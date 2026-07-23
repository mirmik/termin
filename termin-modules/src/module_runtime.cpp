#include "termin_modules/module_runtime.hpp"

#include <tcbase/tc_log.hpp>

#include <algorithm>
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

const char* module_kind_name(ModuleKind kind) {
    switch (kind) {
        case ModuleKind::Cpp: return "cpp";
        case ModuleKind::Python: return "python";
    }
    return "unknown";
}

const char* module_state_name(ModuleState state) {
    switch (state) {
        case ModuleState::Discovered: return "discovered";
        case ModuleState::Loading: return "loading";
        case ModuleState::Loaded: return "loaded";
        case ModuleState::Unloading: return "unloading";
        case ModuleState::CleanupFailed: return "cleanup-failed";
        case ModuleState::Failed: return "failed";
        case ModuleState::Unloaded: return "unloaded";
        case ModuleState::Ignored: return "ignored";
    }
    return "unknown";
}

const char* cleanup_phase_name(ModuleCleanupPhase phase) {
    switch (phase) {
        case ModuleCleanupPhase::None: return "none";
        case ModuleCleanupPhase::Prepare: return "prepare";
        case ModuleCleanupPhase::BackendBegin: return "backend-begin";
        case ModuleCleanupPhase::RevokeContributions: return "revoke-contributions";
        case ModuleCleanupPhase::BackendFinish: return "backend-finish";
        case ModuleCleanupPhase::BackendUnload: return "backend-unload";
    }
    return "unknown";
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

    if (!teardown_backend_environments()) {
        return false;
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

    std::vector<std::filesystem::path> descriptor_paths;
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

        descriptor_paths.push_back(entry.path());
        ++it;
    }

    std::sort(descriptor_paths.begin(), descriptor_paths.end());
    std::vector<ModuleRecord> discovered_records;
    discovered_records.reserve(descriptor_paths.size());
    std::unordered_map<std::string, std::filesystem::path> discovered_descriptors;
    discovered_descriptors.reserve(descriptor_paths.size());
    for (const std::filesystem::path& descriptor_path : descriptor_paths) {
        std::string error;
        auto spec = _parser->parse(descriptor_path, error);
        if (!spec.has_value()) {
            _last_error = error;
            emit(ModuleEventKind::Failed, descriptor_path.string(), error);
            continue;
        }

        const auto [existing, inserted] =
            discovered_descriptors.emplace(spec->id, descriptor_path);
        if (!inserted) {
            _last_error = "Duplicate module id '" + spec->id + "' in descriptors '" +
                existing->second.string() + "' and '" + descriptor_path.string() + "'";
            emit(ModuleEventKind::Failed, spec->id, _last_error);
            continue;
        }

        ModuleRecord record;
        record.spec = std::move(*spec);
        discovered_records.push_back(std::move(record));
    }

    if (!_last_error.empty()) {
        return false;
    }

    _records = std::move(discovered_records);
    if (!prepare_backend_environments()) {
        return false;
    }

    for (const ModuleRecord& record : _records) {
        emit(
            ModuleEventKind::Discovered,
            record.spec.id,
            record.spec.descriptor_path.string()
        );
    }
    return true;
}

bool ModuleRuntime::shutdown() {
    const std::vector<std::string> ordered = build_shutdown_order(_records);
    if (ordered.empty() && !_backend_environments_prepared) {
        _last_error.clear();
        return true;
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

    bool has_active_handles = false;
    for (const ModuleRecord& record : _records) {
        if (is_loaded_or_holding_handle(record)) {
            has_active_handles = true;
            break;
        }
    }
    if (!has_active_handles && !teardown_backend_environments()) {
        failures.push_back(_last_error.empty() ? "environment teardown failed" : _last_error);
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

bool ModuleRuntime::prepare_backend_environments() {
    for (auto& [kind, backend] : _backends) {
        std::string diagnostics;
        std::string error;
        if (backend->prepare_environment(_records, _environment, diagnostics, error)) {
            continue;
        }

        for (ModuleRecord& record : _records) {
            if (record.spec.kind == kind) {
                record.diagnostics = diagnostics;
            }
        }
        _last_error = "Failed to prepare module environment: " +
            (error.empty() ? std::string("backend setup failed") : error);
        tc::Log::error("ModuleRuntime: %s", _last_error.c_str());

        for (auto& [rollback_kind, rollback_backend] : _backends) {
            (void)rollback_kind;
            std::string rollback_error;
            if (!rollback_backend->teardown_environment(_environment, rollback_error)) {
                tc::Log::error(
                    "ModuleRuntime: environment rollback failed: %s",
                    rollback_error.c_str()
                );
            }
        }
        _backend_environments_prepared = false;
        return false;
    }
    _backend_environments_prepared = true;
    _last_error.clear();
    return true;
}

bool ModuleRuntime::teardown_backend_environments() {
    if (!_backend_environments_prepared) {
        return true;
    }
    std::vector<std::string> errors;
    for (auto& [kind, backend] : _backends) {
        (void)kind;
        std::string error;
        if (!backend->teardown_environment(_environment, error)) {
            errors.push_back(error.empty() ? "backend teardown failed" : error);
        }
    }
    if (errors.empty()) {
        _backend_environments_prepared = false;
        _last_error.clear();
        return true;
    }

    std::ostringstream message;
    message << "Failed to teardown module environment";
    for (const std::string& error : errors) {
        message << "; " << error;
    }
    _last_error = message.str();
    tc::Log::error("ModuleRuntime: %s", _last_error.c_str());
    return false;
}

bool ModuleRuntime::load_all() {
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

    if (target->state == ModuleState::Unloading ||
        target->state == ModuleState::CleanupFailed ||
        target->cleanup_phase != ModuleCleanupPhase::None) {
        target->error_message =
            "Module cleanup is incomplete at phase '" +
            std::string(cleanup_phase_name(target->cleanup_phase)) +
            "'; call unload_module to resume cleanup: " + module_id;
        _last_error = target->error_message;
        emit(ModuleEventKind::Failed, module_id, target->error_message);
        return false;
    }

    if (target->state == ModuleState::Loading) {
        target->error_message = "Module is already loading: " + module_id;
        _last_error = target->error_message;
        emit(ModuleEventKind::Failed, module_id, target->error_message);
        return false;
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

    target->state = ModuleState::Loading;
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
    bool cpp_load_failure_handled = false;
    if (target->spec.kind == ModuleKind::Cpp) {
        load_environment.before_cpp_module_init = _cpp_callbacks.before_native_init;
        load_environment.after_cpp_module_init = _cpp_callbacks.after_native_init;
        load_environment.on_cpp_module_load_failure =
            [this, &cpp_load_failure_handled](
                const ModuleRecord& record,
                const std::string& error,
                std::string& cleanup_error
            ) {
                cpp_load_failure_handled = true;
                if (_cpp_callbacks.after_failed_load) {
                    return _cpp_callbacks.after_failed_load(record, error, cleanup_error);
                }
                return true;
            };
    }

    if (!backend->load(*target, load_environment)) {
        if (target->error_message.empty()) {
            target->error_message = "Backend load failed";
        }
        if (target->spec.kind == ModuleKind::Cpp) {
            if (!cpp_load_failure_handled && _cpp_callbacks.after_failed_load) {
                std::string cleanup_error;
                if (!_cpp_callbacks.after_failed_load(
                        *target,
                        target->error_message,
                        cleanup_error
                    ) && !cleanup_error.empty()) {
                    target->error_message += "; " + cleanup_error;
                }
            }
        } else {
            if (_python_callbacks.after_failed_load) {
                std::string cleanup_error;
                if (!_python_callbacks.after_failed_load(
                        *target,
                        target->error_message,
                        cleanup_error
                    ) && !cleanup_error.empty()) {
                    target->error_message += "; " + cleanup_error;
                }
            }
        }
        if (target->handle) {
            const std::string load_error = target->error_message;
            target->state = ModuleState::CleanupFailed;
            target->cleanup_phase =
                target->spec.kind == ModuleKind::Cpp && backend->supports_staged_unload()
                    ? ModuleCleanupPhase::BackendBegin
                    : ModuleCleanupPhase::BackendUnload;
            if (unload_module_impl(module_id, false)) {
                target = find_mutable_record(_records, module_id);
                target->state = ModuleState::Failed;
                target->cleanup_phase = ModuleCleanupPhase::None;
                target->error_message = load_error;
                _last_error = load_error;
                emit(ModuleEventKind::Failed, module_id, load_error);
            } else {
                target = find_mutable_record(_records, module_id);
                target->error_message = load_error + "; replacement cleanup failed: " +
                    target->error_message + "; call unload_module to complete cleanup";
                _last_error = target->error_message;
                tc::Log::error(
                    "ModuleRuntime: failed load retained module='%s' backend='%s' phase='%s'",
                    module_id.c_str(),
                    module_kind_name(target->spec.kind),
                    cleanup_phase_name(target->cleanup_phase)
                );
            }
        } else {
            target->state = ModuleState::Failed;
            target->cleanup_phase = ModuleCleanupPhase::None;
            _last_error = target->error_message;
            emit(ModuleEventKind::Failed, module_id, target->error_message);
        }
        return false;
    }

    target->state = ModuleState::Loaded;
    target->cleanup_phase = ModuleCleanupPhase::None;
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

    const ModuleState original_state = target->state;
    const bool retrying_cleanup = target->state == ModuleState::CleanupFailed;
    if (target->state == ModuleState::Loading) {
        target->error_message = "Cannot unload module while it is loading: " + module_id;
        _last_error = target->error_message;
        emit(ModuleEventKind::Failed, module_id, target->error_message);
        return false;
    }
    if (target->state == ModuleState::Unloading) {
        target->error_message = "Module unload is already in progress: " + module_id;
        _last_error = target->error_message;
        emit(ModuleEventKind::Failed, module_id, target->error_message);
        return false;
    }
    if (!retrying_cleanup && target->state != ModuleState::Loaded && !target->handle) {
        target->state = ModuleState::Unloaded;
        target->cleanup_phase = ModuleCleanupPhase::None;
        target->error_message.clear();
        return true;
    }

    auto log_failure = [&](ModuleCleanupPhase phase, bool after_boundary) {
        tc::Log::error(
            "ModuleRuntime: unload failure module='%s' backend='%s' phase='%s' "
            "retained_handle=%s boundary=%s error='%s'",
            module_id.c_str(),
            module_kind_name(target->spec.kind),
            cleanup_phase_name(phase),
            target->handle ? "yes" : "no",
            after_boundary ? "crossed" : "not-crossed",
            target->error_message.c_str()
        );
    };
    auto fail_after_boundary = [&](const std::string& fallback) {
        if (target->error_message.empty()) target->error_message = fallback;
        target->state = ModuleState::CleanupFailed;
        _last_error = target->error_message;
        log_failure(target->cleanup_phase, true);
        emit(ModuleEventKind::CleanupFailed, module_id, target->error_message);
        return false;
    };
    auto fail_before_boundary = [&](const std::string& message) {
        target->state = original_state;
        target->cleanup_phase = ModuleCleanupPhase::None;
        target->error_message = message;
        _last_error = target->error_message;
        log_failure(ModuleCleanupPhase::Prepare, false);
        emit(ModuleEventKind::Failed, module_id, target->error_message);
        return false;
    };

    IModuleBackend* backend = get_backend(target->spec.kind);
    if (backend == nullptr) {
        if (retrying_cleanup) {
            return fail_after_boundary("Backend is not registered");
        }
        return fail_before_boundary("Backend is not registered");
    }

    if (!retrying_cleanup) {
        const std::vector<std::string> dependents =
            collect_active_dependents(_records, module_id);
        if (!dependents.empty()) {
            std::string message = "Active dependents prevent unload: ";
            for (size_t i = 0; i < dependents.size(); ++i) {
                if (i > 0) message += ", ";
                message += dependents[i];
            }
            return fail_before_boundary(message);
        }

        target->cleanup_phase = ModuleCleanupPhase::Prepare;
        if (target->spec.kind == ModuleKind::Cpp) {
            if (_cpp_callbacks.before_unload) {
                std::string error;
                if (!_cpp_callbacks.before_unload(*target, error)) {
                    return fail_before_boundary(
                        error.empty() ? "C++ module unload preparation failed" : error
                    );
                }
            }
        } else {
            if (_python_callbacks.before_unload) {
                _python_callbacks.before_unload(*target);
            }
            if (_python_callbacks.before_module_remove) {
                std::string error;
                if (!_python_callbacks.before_module_remove(*target, error)) {
                    return fail_before_boundary(
                        error.empty() ? "Python module unload preparation failed" : error
                    );
                }
            }
        }

        target->state = ModuleState::Unloading;
        target->cleanup_phase =
            target->spec.kind == ModuleKind::Cpp && backend->supports_staged_unload()
                ? ModuleCleanupPhase::BackendBegin
                : ModuleCleanupPhase::BackendUnload;
        target->error_message.clear();
        emit(ModuleEventKind::Unloading, module_id);
    } else {
        target->state = ModuleState::Unloading;
        target->error_message.clear();
        emit(
            ModuleEventKind::Unloading,
            module_id,
            "Retrying cleanup phase: " +
                std::string(cleanup_phase_name(target->cleanup_phase))
        );
    }

    if (target->cleanup_phase == ModuleCleanupPhase::BackendBegin) {
        if (!backend->begin_unload(*target, _environment)) {
            return fail_after_boundary("Backend begin_unload failed");
        }
        target->cleanup_phase = ModuleCleanupPhase::RevokeContributions;
    }

    if (target->cleanup_phase == ModuleCleanupPhase::RevokeContributions) {
        if (_cpp_callbacks.before_native_close) {
            std::string error;
            if (!_cpp_callbacks.before_native_close(*target, error)) {
                if (!error.empty()) target->error_message = error;
                return fail_after_boundary("Contribution revoke failed");
            }
        }
        target->cleanup_phase = ModuleCleanupPhase::BackendFinish;
    }

    if (target->cleanup_phase == ModuleCleanupPhase::BackendFinish) {
        if (!backend->finish_unload(*target, _environment)) {
            return fail_after_boundary("Backend finish_unload failed");
        }
    } else if (target->cleanup_phase == ModuleCleanupPhase::BackendUnload) {
        if (!backend->unload(*target, _environment)) {
            return fail_after_boundary("Backend unload failed");
        }
    } else {
        return fail_after_boundary(
            "Invalid cleanup phase: " +
            std::string(cleanup_phase_name(target->cleanup_phase))
        );
    }

    target->state = ModuleState::Unloaded;
    target->cleanup_phase = ModuleCleanupPhase::None;
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
    if (!refresh_descriptor_snapshot()) {
        return false;
    }

    if (find(module_id) == nullptr) {
        _last_error = "Module not found: " + module_id;
        return false;
    }
    return execute_reload({module_id});
}

bool ModuleRuntime::reload_module_with_dependents(const std::string& module_id) {
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

    return execute_reload(ordered);
}

bool ModuleRuntime::execute_reload(const std::vector<std::string>& ordered_module_ids) {
    std::unordered_map<std::string, std::shared_ptr<IModuleReloadState>> reload_states;
    reload_states.reserve(ordered_module_ids.size());

    // Capture every affected generation before crossing the first semantic
    // unload boundary. Single-module and cascade reload deliberately share
    // this exact orchestration path.
    for (const std::string& module_id : ordered_module_ids) {
        const ModuleRecord* record = find(module_id);
        if (record == nullptr) {
            _last_error = "Module not found: " + module_id;
            emit(ModuleEventKind::Failed, module_id, _last_error);
            return false;
        }
        if (record->state == ModuleState::CleanupFailed ||
            record->state == ModuleState::Unloading ||
            record->cleanup_phase != ModuleCleanupPhase::None) {
            _last_error = "Cannot reload module while cleanup is incomplete at phase '" +
                std::string(cleanup_phase_name(record->cleanup_phase)) +
                "'; call unload_module first: " + module_id;
            emit(ModuleEventKind::Failed, module_id, _last_error);
            return false;
        }
        emit(ModuleEventKind::Reloading, module_id);
        reload_states.emplace(module_id, capture_reload_state(*record));
    }

    // Unload the complete affected graph before attempting any replacement
    // load. An unload failure leaves the already processed records Unloaded,
    // the failing record in its precise failure state, and the untouched tail
    // active; no new generation has started yet.
    for (auto it = ordered_module_ids.rbegin(); it != ordered_module_ids.rend(); ++it) {
        const ModuleRecord* record = find(*it);
        if (record == nullptr) {
            _last_error = "Module not found while unloading reload plan: " + *it;
            emit(ModuleEventKind::Failed, *it, _last_error);
            return false;
        }
        if (is_loaded_or_holding_handle(*record) && !unload_module_impl(*it, false)) {
            return false;
        }
    }

    if (!require_completed_reload_unload(ordered_module_ids)) {
        return false;
    }

    for (const std::string& module_id : ordered_module_ids) {
        if (!load_module_impl(module_id, false)) {
            return false;
        }

        const auto state_it = reload_states.find(module_id);
        const std::shared_ptr<IModuleReloadState> reload_state =
            state_it != reload_states.end() ? state_it->second : nullptr;
        if (!restore_reload_state(module_id, reload_state)) {
            return false;
        }
    }

    return true;
}

bool ModuleRuntime::require_completed_reload_unload(
    const std::vector<std::string>& module_ids
) {
    for (const std::string& module_id : module_ids) {
        const ModuleRecord* record = find(module_id);
        if (record == nullptr) {
            _last_error = "Module disappeared before replacement load: " + module_id;
            emit(ModuleEventKind::Failed, module_id, _last_error);
            return false;
        }
        const bool inactive_state =
            record->state != ModuleState::Loaded &&
            record->state != ModuleState::Loading &&
            record->state != ModuleState::Unloading &&
            record->state != ModuleState::CleanupFailed;
        if (inactive_state && record->cleanup_phase == ModuleCleanupPhase::None && !record->handle) {
            continue;
        }

        _last_error = "Replacement load blocked because old module generation did not reach "
            "completed unload: module='" + module_id + "' state='" +
            module_state_name(record->state) + "' phase='" +
            cleanup_phase_name(record->cleanup_phase) + "' retained_handle=" +
            (record->handle ? "yes" : "no");
        tc::Log::error("ModuleRuntime: %s", _last_error.c_str());
        emit(ModuleEventKind::Failed, module_id, _last_error);
        return false;
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
    if (target->state == ModuleState::Unloading ||
        target->state == ModuleState::CleanupFailed ||
        target->cleanup_phase != ModuleCleanupPhase::None) {
        _last_error = "Cannot build module while cleanup is incomplete: " + module_id;
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
    if (target->state == ModuleState::Loaded ||
        target->state == ModuleState::Loading ||
        target->state == ModuleState::Unloading ||
        target->state == ModuleState::CleanupFailed ||
        target->cleanup_phase != ModuleCleanupPhase::None) {
        _last_error = "Cannot clean active module or module with incomplete cleanup; "
            "finish unload first: " + module_id;
        return false;
    }

    IModuleBackend* backend = get_backend(target->spec.kind);
    if (backend == nullptr) {
        _last_error = "Backend is not registered";
        return false;
    }

    if (backend->clean(*target, _environment) == ModuleCleanResult::Failed) {
        if (target->error_message.empty()) {
            target->error_message = "Clean failed";
        }
        _last_error = target->error_message;
        return false;
    }

    return true;
}

bool ModuleRuntime::rebuild_module(const std::string& module_id) {
    if (!refresh_descriptor_snapshot()) {
        return false;
    }
    ModuleRecord* target = find_mutable_record(_records, module_id);
    if (target == nullptr) {
        _last_error = "Module not found: " + module_id;
        return false;
    }
    if (target->state == ModuleState::Unloading ||
        target->state == ModuleState::CleanupFailed ||
        target->cleanup_phase != ModuleCleanupPhase::None) {
        _last_error = "Cannot rebuild module while cleanup is incomplete: " + module_id;
        return false;
    }
    const bool was_loaded = target->state == ModuleState::Loaded;
    if (was_loaded && !unload_module(module_id)) {
        return false;
    }

    // A backend may intentionally have no clean step, but an attempted clean
    // must succeed before a rebuild can reuse its artifact location.
    if (!clean_module(module_id)) {
        return false;
    }

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

bool ModuleRuntime::resolve_closure(
    const std::vector<std::string>& root_module_ids,
    std::vector<const ModuleRecord*>& ordered
) {
    ordered.clear();
    _last_error.clear();

    std::vector<std::string> roots = root_module_ids;
    std::sort(roots.begin(), roots.end());
    roots.erase(std::unique(roots.begin(), roots.end()), roots.end());

    std::unordered_map<std::string, int> marks;
    std::vector<std::string> stack;
    for (const std::string& root : roots) {
        const ModuleRecord* record = find(root);
        if (record == nullptr) {
            _last_error = "Selected module not found: " + root;
            tc::Log::error("ModuleRuntime: closure resolution failed: %s", _last_error.c_str());
            return false;
        }
        if (!visit_closure_module(*record, marks, ordered, stack, _last_error)) {
            tc::Log::error("ModuleRuntime: closure resolution failed: %s", _last_error.c_str());
            ordered.clear();
            return false;
        }
    }
    return true;
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

bool ModuleRuntime::visit_closure_module(
    const ModuleRecord& record,
    std::unordered_map<std::string, int>& marks,
    std::vector<const ModuleRecord*>& ordered,
    std::vector<std::string>& stack,
    std::string& error
) const {
    const int current_mark = marks[record.spec.id];
    if (current_mark == 2) return true;
    if (current_mark == 1) {
        auto cycle_start = std::find(stack.begin(), stack.end(), record.spec.id);
        std::ostringstream message;
        message << "Dependency cycle detected: ";
        for (auto it = cycle_start; it != stack.end(); ++it) {
            if (it != cycle_start) message << " -> ";
            message << *it;
        }
        message << " -> " << record.spec.id;
        error = message.str();
        return false;
    }

    marks[record.spec.id] = 1;
    stack.push_back(record.spec.id);
    std::vector<std::string> dependencies = record.spec.dependencies;
    std::sort(dependencies.begin(), dependencies.end());
    dependencies.erase(std::unique(dependencies.begin(), dependencies.end()), dependencies.end());
    for (const std::string& dependency : dependencies) {
        const ModuleRecord* dependency_record = find(dependency);
        if (dependency_record == nullptr) {
            error = "Missing dependency '" + dependency + "' for module '" + record.spec.id + "'";
            return false;
        }
        if (!visit_closure_module(*dependency_record, marks, ordered, stack, error)) return false;
    }
    stack.pop_back();
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
