#pragma once

#include <filesystem>
#include <functional>
#include <memory>
#include <string>
#include <unordered_map>
#include <vector>

#include "termin_modules/module_backend.hpp"
#include "termin_modules/module_descriptor_parser.hpp"
#include "termin_modules/module_integration.hpp"
#include "termin_modules/termin_modules_api.hpp"

namespace termin_modules {

class TERMIN_MODULES_API ModuleRuntime {
public:
    using ModuleEventCallback = std::function<void(const ModuleEvent&)>;
    using MutationThreadChecker = std::function<bool(std::string&)>;

private:
    ModuleEnvironment _environment;
    CppModuleCallbacks _cpp_callbacks;
    PythonModuleCallbacks _python_callbacks;
    std::shared_ptr<ModuleDescriptorParser> _parser;
    std::unordered_map<ModuleKind, std::shared_ptr<IModuleBackend>> _backends;
    std::vector<ModuleRecord> _records;
    ModuleEventCallback _event_callback;
    BuildOutputCallback _build_output_callback;
    MutationThreadChecker _mutation_thread_checker;
    std::vector<std::filesystem::path> _discovery_ignored_roots;
    std::string _last_error;
    bool _backend_environments_prepared = false;

public:
    ModuleRuntime() = default;
    ~ModuleRuntime() noexcept;

    ModuleRuntime(const ModuleRuntime&) = delete;
    ModuleRuntime& operator=(const ModuleRuntime&) = delete;
    ModuleRuntime(ModuleRuntime&&) = delete;
    ModuleRuntime& operator=(ModuleRuntime&&) = delete;

    void set_environment(ModuleEnvironment environment);
    void set_cpp_callbacks(CppModuleCallbacks callbacks);
    void set_python_callbacks(PythonModuleCallbacks callbacks);
    void set_event_callback(ModuleEventCallback callback);
    void set_build_output_callback(BuildOutputCallback callback);
    void set_mutation_thread_checker(MutationThreadChecker checker);
    void set_descriptor_parser(std::shared_ptr<ModuleDescriptorParser> parser);
    void set_discovery_ignored_roots(std::vector<std::filesystem::path> roots);
    void register_backend(std::shared_ptr<IModuleBackend> backend);

    bool discover(const std::filesystem::path& project_root);
    bool shutdown();

    bool load_all();
    bool load_module(const std::string& module_id);
    bool unload_module(const std::string& module_id);
    bool reload_module(const std::string& module_id);
    bool reload_module_with_dependents(const std::string& module_id);
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
    bool build_reload_order_with_loaded_dependents(
        const std::string& module_id,
        std::vector<std::string>& ordered,
        std::string& error
    );
    bool visit_reload_module(
        const std::string& module_id,
        const std::unordered_map<std::string, bool>& affected,
        std::unordered_map<std::string, int>& marks,
        std::vector<std::string>& ordered,
        std::string& error
    );
    bool visit_module(
        ModuleRecord& record,
        std::unordered_map<std::string, int>& marks,
        std::vector<ModuleRecord*>& ordered,
        std::string& error
    );
    bool refresh_descriptor_snapshot();
    std::shared_ptr<IModuleReloadState> capture_reload_state(const ModuleRecord& record) const;
    bool restore_reload_state(
        const std::string& module_id,
        const std::shared_ptr<IModuleReloadState>& reload_state
    );
    IModuleBackend* get_backend(ModuleKind kind) const;
    void emit(ModuleEventKind kind, const std::string& module_id, const std::string& message = std::string());
    bool should_skip(const ModuleSpec& spec) const;
    bool is_discovery_ignored(const std::filesystem::path& path) const;
    bool load_module_impl(const std::string& module_id, bool refresh_descriptors);
    bool unload_module_impl(const std::string& module_id, bool refresh_descriptor);
    bool ensure_mutation_thread(const char* operation);
    bool prepare_backend_environments();
    bool teardown_backend_environments();
};

} // namespace termin_modules
