// module_loader.hpp - Hot-reload system for C++ modules
#pragma once

// Windows headers must be included first with NOMINMAX to prevent macro conflicts
#ifdef _WIN32
    #ifndef NOMINMAX
        #define NOMINMAX
    #endif
    #ifndef WIN32_LEAN_AND_MEAN
        #define WIN32_LEAN_AND_MEAN
    #endif
    #include <windows.h>
    // Windows.h defines near and far as macros, which conflicts with geometry code
    #undef near
    #undef far
    using ModuleHandle = HMODULE;
#else
    using ModuleHandle = void*;
#endif

#include <string>
#include <vector>
#include <unordered_map>
#include <memory>
#include <functional>

#include "../export.hpp"

namespace termin {

// Module descriptor loaded from .module file
struct ModuleDescriptor {
    std::string name;
    std::string path;                          // Path to .module file
    std::vector<std::string> sources;          // Glob patterns for sources
    std::vector<std::string> include_dirs;     // Additional include directories
    std::vector<std::string> components;       // Component type names
};

// Information about a loaded module
struct LoadedModule {
    std::string name;
    std::string dll_path;                      // Path to loaded DLL
    std::string temp_dll_path;                 // Temporary copy (Windows)
    ModuleHandle handle = nullptr;
    ModuleDescriptor descriptor;
    std::vector<std::string> registered_components;
};

// Callback for module events
using ModuleEventCallback = std::function<void(const std::string& module_name, const std::string& event)>;

class ENTITY_API ModuleLoader {
public:
    static ModuleLoader& instance();

    // Load a module from .module descriptor file
    bool load_module(const std::string& module_path);

    // Unload a module by name
    bool unload_module(const std::string& name);

    // Reload a module (unload + compile + load)
    bool reload_module(const std::string& name);

    // Compile a module, returns path to DLL or empty string on error
    std::string compile_module(const std::string& name);

    // Get last error message
    const std::string& last_error() const { return _last_error; }

    // Get compiler output from last compilation
    const std::string& compiler_output() const { return _compiler_output; }

    // Get list of loaded modules
    std::vector<std::string> list_modules() const;

    // Get module info
    const LoadedModule* get_module(const std::string& name) const;

    // Check if a module is loaded
    bool is_loaded(const std::string& name) const;

    // Set callback for module events
    void set_event_callback(ModuleEventCallback callback);

    // Get C API include directory (core_c/include)
    const std::string& get_core_c() const { return _core_c; }

    // Get C++ include directory (cpp/)
    const std::string& get_core_cpp() const { return _core_cpp; }

    // Get engine library directory
    const std::string& get_lib_dir() const { return _lib_dir; }

    // Set engine paths
    void set_engine_paths(
        const std::string& core_c,
        const std::string& core_cpp,
        const std::string& lib_dir
    );

private:
    ModuleLoader() = default;
    ModuleLoader(const ModuleLoader&) = delete;
    ModuleLoader& operator=(const ModuleLoader&) = delete;

    // Parse .module file
    bool parse_module_file(const std::string& path, ModuleDescriptor& out);

    // DLL operations
    ModuleHandle load_dll(const std::string& path);
    void unload_dll(ModuleHandle handle);
    void* get_symbol(ModuleHandle handle, const char* name);

    // Windows: copy DLL to temp location to avoid file lock
    std::string copy_dll_for_loading(const std::string& path);

    // Clean up temporary DLL files
    void cleanup_temp_dll(const std::string& path);

    // Generate CMakeLists.txt for module
    bool generate_cmake(const ModuleDescriptor& desc, const std::string& build_dir);

    // Run cmake build
    bool run_cmake_build(const std::string& build_dir, const std::string& module_name);

    // Serialize component state before unload
    void serialize_module_components(const std::string& module_name);

    // Restore component state after load
    void restore_module_components(const std::string& module_name);

    // Emit event
    void emit_event(const std::string& module_name, const std::string& event);

    std::unordered_map<std::string, LoadedModule> _modules;
    std::string _last_error;
    std::string _compiler_output;
    std::string _core_c;
    std::string _core_cpp;
    std::string _lib_dir;
    ModuleEventCallback _event_callback;

    // Serialized component state (entity_uuid -> component_type -> serialized_data)
    struct SerializedComponent {
        std::string entity_uuid;
        std::string component_type;
        std::string serialized_data;  // JSON
    };
    std::vector<SerializedComponent> _serialized_state;
};

} // namespace termin
