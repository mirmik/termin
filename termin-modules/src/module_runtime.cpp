#include "termin_modules/module_runtime.hpp"

#include <filesystem>

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

} // namespace

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

void ModuleRuntime::set_descriptor_parser(std::shared_ptr<ModuleDescriptorParser> parser) {
    _parser = std::move(parser);
}

void ModuleRuntime::register_backend(std::shared_ptr<IModuleBackend> backend) {
    if (!backend) {
        return;
    }

    _backends[backend->kind()] = std::move(backend);
}

void ModuleRuntime::discover(const std::filesystem::path& project_root) {
    _records.clear();
    _last_error.clear();

    if (!_parser) {
        _parser = std::make_shared<ModuleDescriptorParser>();
    }

    if (!std::filesystem::exists(project_root)) {
        _last_error = "Project root does not exist: " + project_root.string();
        return;
    }

    std::filesystem::recursive_directory_iterator it(project_root);
    std::filesystem::recursive_directory_iterator end;
    while (it != end) {
        const auto& entry = *it;
        if (entry.is_directory()) {
            const std::string dirname = entry.path().filename().string();
            if (dirname == "build" || dirname == "__pycache__" || is_hidden_dir(entry.path())) {
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
}

bool ModuleRuntime::load_all() {
    std::vector<ModuleRecord*> ordered;
    std::string error;
    if (!build_load_order(ordered, error)) {
        _last_error = error;
        return false;
    }

    bool success = true;
    for (ModuleRecord* record : ordered) {
        if (!load_module(record->spec.id)) {
            success = false;
        }
    }

    return success;
}

bool ModuleRuntime::load_module(const std::string& module_id) {
    ModuleRecord* target = find_mutable_record(_records, module_id);
    if (target == nullptr) {
        _last_error = "Module not found: " + module_id;
        return false;
    }

    if (target->state == ModuleState::Loaded) {
        return true;
    }

    if (should_skip(target->spec)) {
        target->state = ModuleState::Unloaded;
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

    if (!backend->load(*target, _environment)) {
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
    ModuleRecord* target = find_mutable_record(_records, module_id);
    if (target == nullptr) {
        _last_error = "Module not found: " + module_id;
        return false;
    }

    if (target->state != ModuleState::Loaded) {
        target->state = ModuleState::Unloaded;
        return true;
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
    }

    if (!backend->unload(*target, _environment)) {
        if (target->error_message.empty()) {
            target->error_message = "Backend unload failed";
        }
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
    emit(ModuleEventKind::Reloading, module_id);

    const ModuleRecord* current = find(module_id);
    if (current == nullptr) {
        _last_error = "Module not found: " + module_id;
        return false;
    }

    std::shared_ptr<IModuleReloadState> reload_state;
    if (current->spec.kind == ModuleKind::Cpp) {
        if (_cpp_callbacks.capture_reload_state) {
            reload_state = _cpp_callbacks.capture_reload_state(*current);
        }
    } else {
        if (_python_callbacks.capture_reload_state) {
            reload_state = _python_callbacks.capture_reload_state(*current);
        }
    }

    const bool was_loaded = current->state == ModuleState::Loaded;
    if (was_loaded && !unload_module(module_id)) {
        return false;
    }

    if (!load_module(module_id)) {
        return false;
    }

    const ModuleRecord* reloaded = find(module_id);
    if (reloaded == nullptr) {
        return false;
    }

    if (reloaded->spec.kind == ModuleKind::Cpp) {
        if (_cpp_callbacks.restore_reload_state) {
            std::string error;
            if (!_cpp_callbacks.restore_reload_state(*reloaded, reload_state, error)) {
                _last_error = error.empty() ? "Failed to restore C++ reload state" : error;
                return false;
            }
        }
        if (_cpp_callbacks.after_reload) {
            _cpp_callbacks.after_reload(*reloaded);
        }
    } else {
        if (_python_callbacks.restore_reload_state) {
            std::string error;
            if (!_python_callbacks.restore_reload_state(*reloaded, reload_state, error)) {
                _last_error = error.empty() ? "Failed to restore Python reload state" : error;
                return false;
            }
        }
        if (_python_callbacks.after_reload) {
            _python_callbacks.after_reload(*reloaded);
        }
    }

    return true;
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

bool ModuleRuntime::should_skip(const ModuleSpec& spec) const {
    if (spec.kind == ModuleKind::Cpp) {
        const auto config = std::dynamic_pointer_cast<CppModuleConfig>(spec.config);
        return config && config->ignored;
    }

    const auto config = std::dynamic_pointer_cast<PythonModuleConfig>(spec.config);
    return config && config->ignored;
}

const CppModuleCallbacks* ModuleRuntime::get_cpp_callbacks() const {
    return &_cpp_callbacks;
}

const PythonModuleCallbacks* ModuleRuntime::get_python_callbacks() const {
    return &_python_callbacks;
}

} // namespace termin_modules
