#include "termin_modules/module_runtime.hpp"

#include <tcbase/tc_log.hpp>

#include <exception>
#include <filesystem>
#include <sstream>
#include <unordered_map>
#include <unordered_set>

namespace termin_modules {
namespace {

ModuleRecord* find_mutable_record(std::vector<ModuleRecord>& records, const std::string& module_id) {
    for (auto& record : records) {
        if (record.spec.id == module_id) {
            return &record;
        }
    }

    return nullptr;
}

bool is_hidden_dir(const std::filesystem::path& path) {
    const std::string name = path.filename().string();
    return !name.empty() && name[0] == '.';
}

std::filesystem::path normalize_discovery_path(const std::filesystem::path& path) {
    std::error_code ec;
    auto normalized = std::filesystem::weakly_canonical(path, ec);
    if (!ec) {
        return normalized;
    }

    auto absolute = std::filesystem::absolute(path, ec);
    if (!ec) {
        return absolute.lexically_normal();
    }

    return path.lexically_normal();
}

bool is_same_or_child_path(
    const std::filesystem::path& path,
    const std::filesystem::path& parent
) {
    auto path_it = path.begin();
    auto parent_it = parent.begin();
    for (; parent_it != parent.end(); ++parent_it, ++path_it) {
        if (path_it == path.end() || *path_it != *parent_it) {
            return false;
        }
    }
    return true;
}

std::vector<std::string> collect_active_dependents(
    const std::vector<ModuleRecord>& records,
    const std::string& module_id
) {
    std::vector<std::string> dependents;

    for (const ModuleRecord& record : records) {
        if (record.state != ModuleState::Loaded && record.handle == nullptr) {
            continue;
        }

        for (const std::string& dependency : record.spec.dependencies) {
            if (dependency == module_id) {
                dependents.push_back(record.spec.id);
                break;
            }
        }
    }

    return dependents;
}

bool is_loaded_or_holding_handle(const ModuleRecord& record) {
    return record.state == ModuleState::Loaded || record.handle != nullptr;
}

std::vector<std::string> build_shutdown_order(const std::vector<ModuleRecord>& records) {
    std::unordered_set<std::string> remaining;
    for (const ModuleRecord& record : records) {
        if (is_loaded_or_holding_handle(record)) {
            remaining.insert(record.spec.id);
        }
    }

    std::vector<std::string> ordered;
    ordered.reserve(remaining.size());
    while (!remaining.empty()) {
        bool made_progress = false;
        for (const ModuleRecord& candidate : records) {
            if (!remaining.contains(candidate.spec.id)) {
                continue;
            }

            bool has_active_dependent = false;
            for (const ModuleRecord& possible_dependent : records) {
                if (!remaining.contains(possible_dependent.spec.id)) {
                    continue;
                }
                for (const std::string& dependency : possible_dependent.spec.dependencies) {
                    if (dependency == candidate.spec.id) {
                        has_active_dependent = true;
                        break;
                    }
                }
                if (has_active_dependent) {
                    break;
                }
            }

            if (!has_active_dependent) {
                ordered.push_back(candidate.spec.id);
                remaining.erase(candidate.spec.id);
                made_progress = true;
            }
        }

        if (made_progress) {
            continue;
        }

        // Invalid/cyclic descriptor graphs must not make destruction throw or
        // silently discard handles. Keep deterministic record order and let
        // unload guards produce actionable diagnostics for every survivor.
        for (const ModuleRecord& record : records) {
            if (remaining.erase(record.spec.id) > 0) {
                ordered.push_back(record.spec.id);
            }
        }
    }

    return ordered;
}

} // namespace

ModuleRuntime::~ModuleRuntime() noexcept {
    try {
        if (!shutdown()) {
            tc::Log::error(
                "ModuleRuntime: shutdown during destruction failed; active module handles are being abandoned: %s",
                _last_error.c_str()
            );
        }
    } catch (const std::exception& e) {
        tc::Log::error(e, "ModuleRuntime: exception during non-throwing destruction shutdown");
    } catch (...) {
        tc::Log::error("ModuleRuntime: unknown exception during non-throwing destruction shutdown");
    }
}

void ModuleRuntime::set_environment(ModuleEnvironment environment) {
    _environment = std::move(environment);
}

void ModuleRuntime::set_cpp_callbacks(CppModuleCallbacks callbacks) {
    _cpp_callbacks = std::move(callbacks);
}

void ModuleRuntime::set_python_callbacks(PythonModuleCallbacks callbacks) {
    _python_callbacks = std::move(callbacks);
}

void ModuleRuntime::set_event_callback(ModuleEventCallback callback) {
    _event_callback = std::move(callback);
}

void ModuleRuntime::set_build_output_callback(BuildOutputCallback callback) {
    _build_output_callback = callback;
    for (auto& [kind, backend] : _backends) {
        backend->set_output_callback(callback);
    }
}

void ModuleRuntime::set_mutation_thread_checker(MutationThreadChecker checker) {
    _mutation_thread_checker = std::move(checker);
}

void ModuleRuntime::set_descriptor_parser(std::shared_ptr<ModuleDescriptorParser> parser) {
    _parser = std::move(parser);
}

void ModuleRuntime::set_discovery_ignored_roots(std::vector<std::filesystem::path> roots) {
    _discovery_ignored_roots.clear();
    _discovery_ignored_roots.reserve(roots.size());
    for (const auto& root : roots) {
        _discovery_ignored_roots.push_back(normalize_discovery_path(root));
    }
}

void ModuleRuntime::register_backend(std::shared_ptr<IModuleBackend> backend) {
    if (!backend) {
        return;
    }

    if (_build_output_callback) {
        backend->set_output_callback(_build_output_callback);
    }
    _backends[backend->kind()] = std::move(backend);
}

bool ModuleRuntime::discover(const std::filesystem::path& project_root) {
    for (const ModuleRecord& record : _records) {
        if (is_loaded_or_holding_handle(record)) {
            _last_error = "Cannot discover modules while active backend handles exist; call shutdown first";
            emit(ModuleEventKind::Failed, record.spec.id, _last_error);
            return false;
        }
    }

    _records.clear();
    _last_error.clear();

    if (!_parser) {
        _parser = std::make_shared<ModuleDescriptorParser>();
    }

    if (!std::filesystem::exists(project_root)) {
        _last_error = "Project root does not exist: " + project_root.string();
        return false;
    }

    std::filesystem::recursive_directory_iterator it(project_root);
    std::filesystem::recursive_directory_iterator end;
    while (it != end) {
        const auto& entry = *it;
        if (is_discovery_ignored(entry.path())) {
            if (entry.is_directory()) {
                it.disable_recursion_pending();
            }
            ++it;
            continue;
        }

        if (entry.is_directory()) {
            const std::string dirname = entry.path().filename().string();
            if (
                dirname == "build" ||
                dirname == "dist" ||
                dirname == "__pycache__" ||
                is_hidden_dir(entry.path())
            ) {
                it.disable_recursion_pending();
            }
            ++it;
            continue;
        }

        if (!entry.is_regular_file()) {
            ++it;
            continue;
        }

        const auto extension = entry.path().extension().string();
        if (extension != ".module" && extension != ".pymodule") {
            ++it;
            continue;
        }

        std::string error;
        auto spec = _parser->parse(entry.path(), error);
        if (!spec.has_value()) {
            _last_error = error;
            emit(ModuleEventKind::Failed, entry.path().string(), error);
            ++it;
            continue;
        }

        if (find(spec->id) != nullptr) {
            _last_error = "Duplicate module id: " + spec->id;
            emit(ModuleEventKind::Failed, spec->id, _last_error);
            ++it;
            continue;
        }

        ModuleRecord record;
        record.spec = std::move(*spec);
        _records.push_back(std::move(record));
        emit(ModuleEventKind::Discovered, _records.back().spec.id, entry.path().string());
        ++it;
    }

    return _last_error.empty();
}

bool ModuleRuntime::shutdown() {
    const std::vector<std::string> ordered = build_shutdown_order(_records);
    if (ordered.empty()) {
        _last_error.clear();
        return true;
    }
    if (!ensure_mutation_thread("shutdown")) {
        return false;
    }

    std::vector<std::string> failures;
    for (const std::string& module_id : ordered) {
        bool unloaded = false;
        try {
            unloaded = unload_module_impl(module_id, false);
        } catch (const std::exception& e) {
            failures.push_back(module_id + ": " + e.what());
            tc::Log::error(e, "ModuleRuntime: exception while shutting down module '%s'", module_id.c_str());
            continue;
        } catch (...) {
            failures.push_back(module_id + ": unknown exception");
            tc::Log::error("ModuleRuntime: unknown exception while shutting down module '%s'", module_id.c_str());
            continue;
        }

        if (!unloaded) {
            const ModuleRecord* record = find(module_id);
            const std::string error = record && !record->error_message.empty()
                ? record->error_message
                : _last_error;
            failures.push_back(module_id + ": " + (error.empty() ? "unload failed" : error));
        }
    }

    for (const ModuleRecord& record : _records) {
        if (!is_loaded_or_holding_handle(record)) {
            continue;
        }
        const std::string prefix = record.spec.id + ": ";
        bool already_reported = false;
        for (const std::string& failure : failures) {
            if (failure.starts_with(prefix)) {
                already_reported = true;
                break;
            }
        }
        if (!already_reported) {
            failures.push_back(prefix + "active handle remains after shutdown");
        }
    }

    if (failures.empty()) {
        _last_error.clear();
        return true;
    }

    std::ostringstream message;
    message << "Module runtime shutdown failed";
    for (const std::string& failure : failures) {
        message << "; " << failure;
    }
    _last_error = message.str();
    tc::Log::error("ModuleRuntime: %s", _last_error.c_str());
    return false;
}

bool ModuleRuntime::load_all() {
    if (!ensure_mutation_thread("load_all")) {
        return false;
    }
    if (!refresh_descriptor_snapshot()) {
        return false;
    }
    std::vector<ModuleRecord*> ordered;
    std::string error;
    if (!build_load_order(ordered, error)) {
        _last_error = error;
        return false;
    }

    bool success = true;
    for (ModuleRecord* record : ordered) {
        if (!load_module_impl(record->spec.id, false)) {
            success = false;
        }
    }

    return success;
}

bool ModuleRuntime::load_module(const std::string& module_id) {
    if (!ensure_mutation_thread("load_module")) {
        return false;
    }
    return load_module_impl(module_id, true);
}

bool ModuleRuntime::load_module_impl(
    const std::string& module_id,
    bool refresh_descriptors
) {
    if (refresh_descriptors && !refresh_descriptor_snapshot()) {
        return false;
    }
    ModuleRecord* target = find_mutable_record(_records, module_id);
    if (target == nullptr) {
        _last_error = "Module not found: " + module_id;
        return false;
    }

    if (target->state == ModuleState::Loaded) {
        return true;
    }

    if (target->handle) {
        target->state = ModuleState::Failed;
        target->error_message = "Module still has an active backend handle: " + module_id;
        _last_error = target->error_message;
        emit(ModuleEventKind::Failed, module_id, target->error_message);
        return false;
    }

    if (should_skip(target->spec)) {
        target->state = ModuleState::Ignored;
        target->error_message.clear();
        return true;
    }

    for (const std::string& dependency : target->spec.dependencies) {
        const ModuleRecord* dep = find(dependency);
        if (dep == nullptr) {
            target->state = ModuleState::Failed;
            target->error_message = "Missing dependency: " + dependency;
            _last_error = target->error_message;
            emit(ModuleEventKind::Failed, module_id, target->error_message);
            return false;
        }

        if (dep->state != ModuleState::Loaded) {
            target->state = ModuleState::Failed;
            target->error_message = "Dependency is not loaded: " + dependency;
            _last_error = target->error_message;
            emit(ModuleEventKind::Failed, module_id, target->error_message);
            return false;
        }
    }

    IModuleBackend* backend = get_backend(target->spec.kind);
    if (backend == nullptr) {
        target->state = ModuleState::Failed;
        target->error_message = "Backend is not registered";
        _last_error = target->error_message;
        emit(ModuleEventKind::Failed, module_id, target->error_message);
        return false;
    }

    emit(ModuleEventKind::Loading, module_id);
    if (target->spec.kind == ModuleKind::Cpp) {
        if (_cpp_callbacks.before_load) {
            _cpp_callbacks.before_load(*target);
        }
    } else {
        if (_python_callbacks.before_load) {
            _python_callbacks.before_load(*target);
        }
    }

    ModuleEnvironment load_environment = _environment;
    if (target->spec.kind == ModuleKind::Cpp) {
        load_environment.before_cpp_module_init = _cpp_callbacks.before_native_init;
        load_environment.after_cpp_module_init = _cpp_callbacks.after_native_init;
    }

    if (!backend->load(*target, load_environment)) {
        target->state = ModuleState::Failed;
        if (target->error_message.empty()) {
            target->error_message = "Backend load failed";
        }
        _last_error = target->error_message;
        if (target->spec.kind == ModuleKind::Cpp) {
            if (_cpp_callbacks.after_failed_load) {
                _cpp_callbacks.after_failed_load(*target, target->error_message);
            }
        } else {
            if (_python_callbacks.after_failed_load) {
                _python_callbacks.after_failed_load(*target, target->error_message);
            }
        }
        emit(ModuleEventKind::Failed, module_id, target->error_message);
        return false;
    }

    target->state = ModuleState::Loaded;
    target->error_message.clear();
    if (target->spec.kind == ModuleKind::Cpp) {
        if (_cpp_callbacks.after_load) {
            _cpp_callbacks.after_load(*target);
        }
    } else {
        if (_python_callbacks.after_load) {
            _python_callbacks.after_load(*target);
        }
    }
    emit(ModuleEventKind::Loaded, module_id);
    return true;
}

bool ModuleRuntime::unload_module(const std::string& module_id) {
    if (!ensure_mutation_thread("unload_module")) {
        return false;
    }
    return unload_module_impl(module_id, true);
}

bool ModuleRuntime::unload_module_impl(
    const std::string& module_id,
    bool refresh_descriptor
) {
    ModuleRecord* target = find_mutable_record(_records, module_id);
    if (target == nullptr) {
        _last_error = "Module not found: " + module_id;
        return false;
    }
    if (refresh_descriptor) {
        if (!refresh_descriptor_snapshot()) {
            return false;
        }
        target = find_mutable_record(_records, module_id);
        if (target == nullptr) {
            _last_error = "Module not found after descriptor refresh: " + module_id;
            return false;
        }
    }

    if (target->state != ModuleState::Loaded && !target->handle) {
        target->state = ModuleState::Unloaded;
        return true;
    }

    const std::vector<std::string> dependents = collect_active_dependents(_records, module_id);
    if (!dependents.empty()) {
        target->error_message = "Active dependents prevent unload: ";
        for (size_t i = 0; i < dependents.size(); ++i) {
            if (i > 0) {
                target->error_message += ", ";
            }
            target->error_message += dependents[i];
        }
        _last_error = target->error_message;
        emit(ModuleEventKind::Failed, module_id, target->error_message);
        return false;
    }

    IModuleBackend* backend = get_backend(target->spec.kind);
    if (backend == nullptr) {
        target->error_message = "Backend is not registered";
        _last_error = target->error_message;
        return false;
    }

    emit(ModuleEventKind::Unloading, module_id);
    if (target->spec.kind == ModuleKind::Cpp) {
        if (_cpp_callbacks.before_unload) {
            _cpp_callbacks.before_unload(*target);
        }
    } else {
        if (_python_callbacks.before_unload) {
            _python_callbacks.before_unload(*target);
        }
        if (_python_callbacks.before_module_remove) {
            std::string error;
            if (!_python_callbacks.before_module_remove(*target, error)) {
                target->error_message = error.empty()
                    ? "Python module unload preparation failed"
                    : error;
                _last_error = target->error_message;
                emit(ModuleEventKind::Failed, module_id, target->error_message);
                return false;
            }
        }
    }

    bool unload_ok = true;
    if (target->spec.kind == ModuleKind::Cpp && backend->supports_staged_unload()) {
        unload_ok = backend->begin_unload(*target, _environment);
        if (unload_ok && _cpp_callbacks.before_native_close) {
            std::string error;
            unload_ok = _cpp_callbacks.before_native_close(*target, error);
            if (!unload_ok && !error.empty()) {
                target->error_message = error;
            }
        }
        if (unload_ok) {
            unload_ok = backend->finish_unload(*target, _environment);
        }
    } else {
        unload_ok = backend->unload(*target, _environment);
    }

    if (!unload_ok) {
        if (target->error_message.empty()) {
            target->error_message = "Backend unload failed";
        }
        target->state = target->spec.kind == ModuleKind::Python && target->handle
            ? ModuleState::Loaded
            : ModuleState::Failed;
        _last_error = target->error_message;
        emit(ModuleEventKind::Failed, module_id, target->error_message);
        return false;
    }

    target->state = ModuleState::Unloaded;
    target->handle.reset();
    target->error_message.clear();
    if (target->spec.kind == ModuleKind::Cpp) {
        if (_cpp_callbacks.after_unload) {
            _cpp_callbacks.after_unload(*target);
        }
    } else {
        if (_python_callbacks.after_unload) {
            _python_callbacks.after_unload(*target);
        }
    }
    emit(ModuleEventKind::Unloaded, module_id);
    return true;
}

bool ModuleRuntime::reload_module(const std::string& module_id) {
    if (!ensure_mutation_thread("reload_module")) {
        return false;
    }
    if (!refresh_descriptor_snapshot()) {
        return false;
    }

    emit(ModuleEventKind::Reloading, module_id);

    const ModuleRecord* current = find(module_id);
    if (current == nullptr) {
        _last_error = "Module not found: " + module_id;
        return false;
    }

    std::shared_ptr<IModuleReloadState> reload_state = capture_reload_state(*current);

    const bool was_loaded = is_loaded_or_holding_handle(*current);
    if (was_loaded && !unload_module_impl(module_id, false)) {
        return false;
    }

    if (!load_module_impl(module_id, false)) {
        return false;
    }

    return restore_reload_state(module_id, reload_state);
}

bool ModuleRuntime::reload_module_with_dependents(const std::string& module_id) {
    if (!ensure_mutation_thread("reload_module_with_dependents")) {
        return false;
    }
    if (!refresh_descriptor_snapshot()) {
        return false;
    }
    std::vector<std::string> ordered;
    std::string error;
    if (!build_reload_order_with_loaded_dependents(module_id, ordered, error)) {
        _last_error = error;
        emit(ModuleEventKind::Failed, module_id, error);
        return false;
    }

    std::unordered_map<std::string, std::shared_ptr<IModuleReloadState>> reload_states;
    for (const std::string& affected_id : ordered) {
        ModuleRecord* record = find_mutable_record(_records, affected_id);
        if (record == nullptr) {
            _last_error = "Module not found: " + affected_id;
            emit(ModuleEventKind::Failed, affected_id, _last_error);
            return false;
        }
        emit(ModuleEventKind::Reloading, affected_id);
        reload_states.emplace(affected_id, capture_reload_state(*record));
    }

    for (auto it = ordered.rbegin(); it != ordered.rend(); ++it) {
        const ModuleRecord* record = find(*it);
        if (record == nullptr) {
            _last_error = "Module not found: " + *it;
            emit(ModuleEventKind::Failed, *it, _last_error);
            return false;
        }
        if (is_loaded_or_holding_handle(*record) && !unload_module_impl(*it, false)) {
            return false;
        }
    }

    for (const std::string& affected_id : ordered) {
        if (!load_module_impl(affected_id, false)) {
            return false;
        }

        const auto state_it = reload_states.find(affected_id);
        const std::shared_ptr<IModuleReloadState> reload_state =
            state_it != reload_states.end() ? state_it->second : nullptr;
        if (!restore_reload_state(affected_id, reload_state)) {
            return false;
        }
    }

    return true;
}

bool ModuleRuntime::needs_rebuild(const std::string& module_id) {
    if (!refresh_descriptor_snapshot()) return false;
    ModuleRecord* mutable_target = find_mutable_record(_records, module_id);
    if (mutable_target == nullptr) return false;

    IModuleBackend* backend = get_backend(mutable_target->spec.kind);
    if (backend == nullptr) return false;

    return backend->needs_rebuild(*mutable_target, _environment);
}

bool ModuleRuntime::build_module(const std::string& module_id) {
    if (!refresh_descriptor_snapshot()) {
        return false;
    }
    ModuleRecord* target = find_mutable_record(_records, module_id);
    if (target == nullptr) {
        _last_error = "Module not found: " + module_id;
        return false;
    }
    IModuleBackend* backend = get_backend(target->spec.kind);
    if (backend == nullptr) {
        _last_error = "Backend is not registered";
        return false;
    }

    if (!backend->build(*target, _environment)) {
        target->state = ModuleState::Failed;
        if (target->error_message.empty()) {
            target->error_message = "Build failed";
        }
        _last_error = target->error_message;
        return false;
    }

    if (target->state == ModuleState::Failed) {
        target->state = ModuleState::Unloaded;
        target->error_message.clear();
    }

    return true;
}

bool ModuleRuntime::clean_module(const std::string& module_id) {
    if (!refresh_descriptor_snapshot()) {
        return false;
    }
    ModuleRecord* target = find_mutable_record(_records, module_id);
    if (target == nullptr) {
        _last_error = "Module not found: " + module_id;
        return false;
    }
    if (target->state == ModuleState::Loaded) {
        _last_error = "Cannot clean loaded module, unload first: " + module_id;
        return false;
    }

    IModuleBackend* backend = get_backend(target->spec.kind);
    if (backend == nullptr) {
        _last_error = "Backend is not registered";
        return false;
    }

    if (!backend->clean(*target, _environment)) {
        if (target->error_message.empty()) {
            target->error_message = "Clean failed";
        }
        _last_error = target->error_message;
        return false;
    }

    return true;
}

bool ModuleRuntime::rebuild_module(const std::string& module_id) {
    if (!ensure_mutation_thread("rebuild_module")) {
        return false;
    }
    if (!refresh_descriptor_snapshot()) {
        return false;
    }
    ModuleRecord* target = find_mutable_record(_records, module_id);
    if (target == nullptr) {
        _last_error = "Module not found: " + module_id;
        return false;
    }
    const bool was_loaded = target->state == ModuleState::Loaded;
    if (was_loaded && !unload_module(module_id)) {
        return false;
    }

    // Clean build artifacts (ignore failure if no clean_command configured)
    clean_module(module_id);

    // Build only, do not load
    return build_module(module_id);
}

const ModuleRecord* ModuleRuntime::find(const std::string& module_id) const {
    for (const auto& record : _records) {
        if (record.spec.id == module_id) {
            return &record;
        }
    }

    return nullptr;
}

std::vector<const ModuleRecord*> ModuleRuntime::list() const {
    std::vector<const ModuleRecord*> result;
    result.reserve(_records.size());
    for (const auto& record : _records) {
        result.push_back(&record);
    }
    return result;
}

const std::string& ModuleRuntime::last_error() const {
    return _last_error;
}

bool ModuleRuntime::build_load_order(std::vector<ModuleRecord*>& ordered, std::string& error) {
    ordered.clear();
    std::unordered_map<std::string, int> marks;

    for (auto& record : _records) {
        marks.emplace(record.spec.id, 0);
    }

    for (auto& record : _records) {
        if (marks[record.spec.id] == 0 && !visit_module(record, marks, ordered, error)) {
            return false;
        }
    }

    return true;
}

bool ModuleRuntime::build_reload_order_with_loaded_dependents(
    const std::string& module_id,
    std::vector<std::string>& ordered,
    std::string& error
) {
    ordered.clear();

    ModuleRecord* target = find_mutable_record(_records, module_id);
    if (target == nullptr) {
        error = "Module not found: " + module_id;
        return false;
    }
    std::unordered_map<std::string, bool> affected;
    std::vector<std::string> pending;
    affected.emplace(module_id, true);
    pending.push_back(module_id);

    for (size_t index = 0; index < pending.size(); ++index) {
        const std::string current_id = pending[index];
        for (const ModuleRecord& record : _records) {
            if (!is_loaded_or_holding_handle(record)) {
                continue;
            }
            if (affected.find(record.spec.id) != affected.end()) {
                continue;
            }

            for (const std::string& dependency : record.spec.dependencies) {
                if (dependency == current_id) {
                    affected.emplace(record.spec.id, true);
                    pending.push_back(record.spec.id);
                    break;
                }
            }
        }
    }

    std::unordered_map<std::string, int> marks;
    for (const auto& entry : affected) {
        marks.emplace(entry.first, 0);
    }

    for (const ModuleRecord& record : _records) {
        if (affected.find(record.spec.id) == affected.end()) {
            continue;
        }
        if (marks[record.spec.id] == 0 && !visit_reload_module(record.spec.id, affected, marks, ordered, error)) {
            return false;
        }
    }

    return true;
}

bool ModuleRuntime::visit_reload_module(
    const std::string& module_id,
    const std::unordered_map<std::string, bool>& affected,
    std::unordered_map<std::string, int>& marks,
    std::vector<std::string>& ordered,
    std::string& error
) {
    const int current_mark = marks[module_id];
    if (current_mark == 2) {
        return true;
    }

    if (current_mark == 1) {
        error = "Dependency cycle detected at module: " + module_id;
        return false;
    }

    ModuleRecord* record = find_mutable_record(_records, module_id);
    if (record == nullptr) {
        error = "Module not found: " + module_id;
        return false;
    }

    marks[module_id] = 1;

    for (const std::string& dependency : record->spec.dependencies) {
        if (affected.find(dependency) == affected.end()) {
            continue;
        }
        if (!visit_reload_module(dependency, affected, marks, ordered, error)) {
            return false;
        }
    }

    marks[module_id] = 2;
    ordered.push_back(module_id);
    return true;
}

bool ModuleRuntime::visit_module(
    ModuleRecord& record,
    std::unordered_map<std::string, int>& marks,
    std::vector<ModuleRecord*>& ordered,
    std::string& error
) {
    const int current_mark = marks[record.spec.id];
    if (current_mark == 2) {
        return true;
    }

    if (current_mark == 1) {
        error = "Dependency cycle detected at module: " + record.spec.id;
        return false;
    }

    marks[record.spec.id] = 1;

    for (const std::string& dependency : record.spec.dependencies) {
        ModuleRecord* dep_record = find_mutable_record(_records, dependency);
        if (dep_record == nullptr) {
            error = "Missing dependency '" + dependency + "' for module '" + record.spec.id + "'";
            return false;
        }

        if (!visit_module(*dep_record, marks, ordered, error)) {
            return false;
        }
    }

    marks[record.spec.id] = 2;
    ordered.push_back(&record);
    return true;
}

IModuleBackend* ModuleRuntime::get_backend(ModuleKind kind) const {
    const auto it = _backends.find(kind);
    return it != _backends.end() ? it->second.get() : nullptr;
}

void ModuleRuntime::emit(ModuleEventKind kind, const std::string& module_id, const std::string& message) {
    if (_event_callback) {
        _event_callback(ModuleEvent{kind, module_id, message});
    }
}

bool ModuleRuntime::ensure_mutation_thread(const char* operation) {
    if (!_mutation_thread_checker) {
        return true;
    }
    std::string error;
    if (_mutation_thread_checker(error)) {
        return true;
    }
    _last_error = error.empty()
        ? std::string("Module runtime mutation called from the wrong thread: ") + operation
        : error + " (operation: " + operation + ")";
    tc::Log::error("ModuleRuntime: %s", _last_error.c_str());
    emit(ModuleEventKind::Failed, "<runtime>", _last_error);
    return false;
}

bool ModuleRuntime::refresh_descriptor_snapshot() {
    if (!_parser || _records.empty()) {
        return true;
    }

    std::vector<ModuleSpec> snapshot;
    snapshot.reserve(_records.size());
    std::unordered_map<std::string, size_t> indices;

    auto fail = [this](const std::string& module_id, const std::string& message) {
        _last_error = message;
        emit(ModuleEventKind::Failed, module_id, message);
        tc::Log::error("ModuleRuntime: descriptor snapshot rejected: %s", message.c_str());
        return false;
    };

    for (size_t index = 0; index < _records.size(); ++index) {
        const ModuleRecord& record = _records[index];
        const std::filesystem::path descriptor = record.spec.descriptor_path;
        if (descriptor.empty()) {
            return fail(record.spec.id, "Module '" + record.spec.id + "' has no descriptor path");
        }

        std::string error;
        auto parsed = _parser->parse(descriptor, error);
        if (!parsed.has_value()) {
            return fail(
                record.spec.id,
                "Failed to parse descriptor '" + descriptor.string() + "': " + error
            );
        }
        const auto [existing, inserted] = indices.emplace(parsed->id, index);
        if (!inserted) {
            return fail(
                parsed->id,
                "Duplicate module id '" + parsed->id + "' in descriptors '" +
                    snapshot[existing->second].descriptor_path.string() + "' and '" +
                    descriptor.string() + "'"
            );
        }
        snapshot.push_back(std::move(*parsed));
    }

    for (size_t index = 0; index < snapshot.size(); ++index) {
        const ModuleRecord& record = _records[index];
        const ModuleSpec& parsed = snapshot[index];
        if (parsed.id != record.spec.id) {
            return fail(
                record.spec.id,
                "Descriptor identity changed at '" + parsed.descriptor_path.string() + "': expected '" +
                    record.spec.id + "', got '" + parsed.id + "'"
            );
        }
        if (is_loaded_or_holding_handle(record) && parsed.kind != record.spec.kind) {
            return fail(
                record.spec.id,
                "Descriptor kind changed while module '" + record.spec.id + "' is loaded: " +
                    parsed.descriptor_path.string()
            );
        }
    }

    std::vector<int> marks(snapshot.size(), 0);
    std::function<bool(size_t)> visit = [&](size_t index) {
        if (marks[index] == 2) return true;
        if (marks[index] == 1) {
            return fail(
                snapshot[index].id,
                "Dependency cycle detected at module '" + snapshot[index].id + "' in descriptor '" +
                    snapshot[index].descriptor_path.string() + "'"
            );
        }
        marks[index] = 1;
        for (const std::string& dependency : snapshot[index].dependencies) {
            const auto dependency_it = indices.find(dependency);
            if (dependency_it == indices.end()) {
                return fail(
                    snapshot[index].id,
                    "Missing dependency '" + dependency + "' for module '" + snapshot[index].id +
                        "' in descriptor '" + snapshot[index].descriptor_path.string() + "'"
                );
            }
            if (!visit(dependency_it->second)) return false;
        }
        marks[index] = 2;
        return true;
    };

    for (size_t index = 0; index < snapshot.size(); ++index) {
        if (!visit(index)) return false;
    }

    for (size_t index = 0; index < snapshot.size(); ++index) {
        _records[index].spec = std::move(snapshot[index]);
    }
    _last_error.clear();
    return true;
}

std::shared_ptr<IModuleReloadState> ModuleRuntime::capture_reload_state(const ModuleRecord& record) const {
    if (record.spec.kind == ModuleKind::Cpp) {
        if (_cpp_callbacks.capture_reload_state) {
            return _cpp_callbacks.capture_reload_state(record);
        }
        return nullptr;
    }

    if (_python_callbacks.capture_reload_state) {
        return _python_callbacks.capture_reload_state(record);
    }
    return nullptr;
}

bool ModuleRuntime::restore_reload_state(
    const std::string& module_id,
    const std::shared_ptr<IModuleReloadState>& reload_state
) {
    const ModuleRecord* reloaded = find(module_id);
    if (reloaded == nullptr) {
        _last_error = "Module not found: " + module_id;
        emit(ModuleEventKind::Failed, module_id, _last_error);
        return false;
    }

    if (reloaded->spec.kind == ModuleKind::Cpp) {
        if (_cpp_callbacks.restore_reload_state) {
            std::string error;
            if (!_cpp_callbacks.restore_reload_state(*reloaded, reload_state, error)) {
                _last_error = error.empty() ? "Failed to restore C++ reload state" : error;
                ModuleRecord* failed = find_mutable_record(_records, module_id);
                if (failed != nullptr) {
                    failed->state = ModuleState::Failed;
                    failed->error_message = _last_error;
                }
                emit(ModuleEventKind::Failed, module_id, _last_error);
                return false;
            }
        }
        if (_cpp_callbacks.after_reload) {
            _cpp_callbacks.after_reload(*reloaded);
        }
        return true;
    }

    if (_python_callbacks.restore_reload_state) {
        std::string error;
        if (!_python_callbacks.restore_reload_state(*reloaded, reload_state, error)) {
            _last_error = error.empty() ? "Failed to restore Python reload state" : error;
            ModuleRecord* failed = find_mutable_record(_records, module_id);
            if (failed != nullptr) {
                failed->state = ModuleState::Failed;
                failed->error_message = _last_error;
            }
            emit(ModuleEventKind::Failed, module_id, _last_error);
            return false;
        }
    }
    if (_python_callbacks.after_reload) {
        _python_callbacks.after_reload(*reloaded);
    }
    return true;
}

bool ModuleRuntime::should_skip(const ModuleSpec& spec) const {
    if (spec.kind == ModuleKind::Cpp) {
        const auto config = std::dynamic_pointer_cast<CppModuleConfig>(spec.config);
        return config && config->ignored;
    }

    const auto config = std::dynamic_pointer_cast<PythonModuleConfig>(spec.config);
    return config && config->ignored;
}

bool ModuleRuntime::is_discovery_ignored(const std::filesystem::path& path) const {
    if (_discovery_ignored_roots.empty()) {
        return false;
    }

    const auto normalized = normalize_discovery_path(path);
    for (const auto& ignored_root : _discovery_ignored_roots) {
        if (is_same_or_child_path(normalized, ignored_root)) {
            return true;
        }
    }
    return false;
}

const CppModuleCallbacks* ModuleRuntime::get_cpp_callbacks() const {
    return &_cpp_callbacks;
}

const PythonModuleCallbacks* ModuleRuntime::get_python_callbacks() const {
    return &_python_callbacks;
}

} // namespace termin_modules
