#pragma once

#include <functional>
#include <memory>
#include <string>
#include <unordered_map>
#include <vector>

#include "termin_modules/module_backend.hpp"
#include "termin_modules/module_descriptor_parser.hpp"
#include "termin_modules/module_integration.hpp"

namespace termin_modules {

class ModuleRuntime {
public:
    using ModuleEventCallback = std::function<void(const ModuleEvent&)>;

private:
    ModuleEnvironment _environment;
    CppModuleCallbacks _cpp_callbacks;
    PythonModuleCallbacks _python_callbacks;
    std::shared_ptr<ModuleDescriptorParser> _parser;
    std::unordered_map<ModuleKind, std::shared_ptr<IModuleBackend>> _backends;
    std::vector<ModuleRecord> _records;
    ModuleEventCallback _event_callback;
    BuildOutputCallback _build_output_callback;
    std::string _last_error;

public:
    void set_environment(ModuleEnvironment environment);
    void set_cpp_callbacks(CppModuleCallbacks callbacks);
    void set_python_callbacks(PythonModuleCallbacks callbacks);
    void set_event_callback(ModuleEventCallback callback);
    void set_build_output_callback(BuildOutputCallback callback);
    void set_descriptor_parser(std::shared_ptr<ModuleDescriptorParser> parser);
    void register_backend(std::shared_ptr<IModuleBackend> backend);

    void discover(const std::filesystem::path& project_root);

    bool load_all();
    bool load_module(const std::string& module_id);
    bool unload_module(const std::string& module_id);
    bool reload_module(const std::string& module_id);
    bool needs_rebuild(const std::string& module_id);
    bool build_module(const std::string& module_id);
    bool clean_module(const std::string& module_id);
    bool rebuild_module(const std::string& module_id);

    const ModuleRecord* find(const std::string& module_id) const;
    std::vector<const ModuleRecord*> list() const;

    const std::string& last_error() const;

private:
    const CppModuleCallbacks* get_cpp_callbacks() const;
    const PythonModuleCallbacks* get_python_callbacks() const;
    bool build_load_order(std::vector<ModuleRecord*>& ordered, std::string& error);
    bool visit_module(
        ModuleRecord& record,
        std::unordered_map<std::string, int>& marks,
        std::vector<ModuleRecord*>& ordered,
        std::string& error
    );
    void refresh_spec(ModuleRecord& record);
    IModuleBackend* get_backend(ModuleKind kind) const;
    void emit(ModuleEventKind kind, const std::string& module_id, const std::string& message = std::string());
    bool should_skip(const ModuleSpec& spec) const;
};

} // namespace termin_modules
