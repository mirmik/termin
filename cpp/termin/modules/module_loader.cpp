// module_loader.cpp - Hot-reload system implementation

// Windows headers must be included first with NOMINMAX to prevent macro conflicts
#ifdef _WIN32
    #ifndef NOMINMAX
        #define NOMINMAX
    #endif
    #ifndef WIN32_LEAN_AND_MEAN
        #define WIN32_LEAN_AND_MEAN
    #endif
    #include <windows.h>
    // Windows.h defines near and far as macros, which conflicts with our code
    #undef near
    #undef far
    #define popen _popen
    #define pclose _pclose
#else
    #include <dlfcn.h>
#endif

#include "module_loader.hpp"
#include "../entity/component_registry.hpp"
#ifdef TERMIN_HAS_NANOBIND
#include "../../../core_c/include/tc_inspect.hpp"
#else
#include "../../../core_c/include/tc_inspect_cpp.hpp"
#endif
#include <tc_log.hpp>

#include <fstream>
#include <sstream>
#include <filesystem>
#include <cstdlib>
#include <chrono>
#include <random>

// Trent library for data structures and YAML/JSON parsing
#include "../../trent/trent.h"
#include "../../trent/yaml.h"

namespace fs = std::filesystem;

namespace termin {

ModuleLoader& ModuleLoader::instance() {
    static ModuleLoader inst;
    return inst;
}

bool ModuleLoader::parse_module_file(const std::string& path, ModuleDescriptor& out) {
    std::ifstream file(path);
    if (!file.is_open()) {
        _last_error = "Cannot open module file: " + path;
        return false;
    }

    std::stringstream buffer;
    buffer << file.rdbuf();
    std::string content = buffer.str();

    nos::trent tr;
    try {
        // JSON is a subset of YAML, so we can use the YAML parser
        tr = nos::yaml::parse(content);
    } catch (const std::exception& e) {
        _last_error = "Failed to parse module file: " + std::string(e.what());
        return false;
    }

    out.path = path;

    // Parse name
    if (tr.contains("name") && tr["name"].is_string()) {
        out.name = tr["name"].as_string();
    } else {
        _last_error = "Module file missing 'name' field";
        return false;
    }

    // Parse sources
    if (tr.contains("sources") && tr["sources"].is_list()) {
        for (const auto& src : tr["sources"].as_list()) {
            if (src.is_string()) {
                out.sources.push_back(src.as_string());
            }
        }
    }

    // Parse include_dirs
    if (tr.contains("include_dirs") && tr["include_dirs"].is_list()) {
        for (const auto& dir : tr["include_dirs"].as_list()) {
            if (dir.is_string()) {
                out.include_dirs.push_back(dir.as_string());
            }
        }
    }

    // Parse components
    if (tr.contains("components") && tr["components"].is_list()) {
        for (const auto& comp : tr["components"].as_list()) {
            if (comp.is_string()) {
                out.components.push_back(comp.as_string());
            }
        }
    }

    return true;
}

ModuleHandle ModuleLoader::load_dll(const std::string& path) {
#ifdef _WIN32
    ModuleHandle handle = LoadLibraryA(path.c_str());
    if (!handle) {
        DWORD error = GetLastError();
        _last_error = "LoadLibrary failed with error code: " + std::to_string(error);
    }
    return handle;
#else
    ModuleHandle handle = dlopen(path.c_str(), RTLD_NOW | RTLD_LOCAL);
    if (!handle) {
        _last_error = "dlopen failed: " + std::string(dlerror());
    }
    return handle;
#endif
}

void ModuleLoader::unload_dll(ModuleHandle handle) {
    if (!handle) return;

#ifdef _WIN32
    FreeLibrary(handle);
#else
    dlclose(handle);
#endif
}

void* ModuleLoader::get_symbol(ModuleHandle handle, const char* name) {
    if (!handle) return nullptr;

#ifdef _WIN32
    return (void*)GetProcAddress(handle, name);
#else
    return dlsym(handle, name);
#endif
}

std::string ModuleLoader::copy_dll_for_loading(const std::string& path) {
#ifdef _WIN32
    // On Windows, DLLs are locked when loaded, so we copy to a temp location
    fs::path src(path);
    if (!fs::exists(src)) {
        _last_error = "DLL file not found: " + path;
        return "";
    }

    // Generate unique temp filename
    auto now = std::chrono::system_clock::now().time_since_epoch().count();
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> dis(0, 9999);

    fs::path temp_dir = fs::temp_directory_path();
    std::string temp_name = src.stem().string() + "_" + std::to_string(now) + "_" + std::to_string(dis(gen)) + ".dll";
    fs::path temp_path = temp_dir / temp_name;

    try {
        fs::copy_file(src, temp_path, fs::copy_options::overwrite_existing);
    } catch (const std::exception& e) {
        _last_error = "Failed to copy DLL: " + std::string(e.what());
        return "";
    }

    return temp_path.string();
#else
    // On Linux/macOS, no need to copy
    return path;
#endif
}

void ModuleLoader::cleanup_temp_dll(const std::string& path) {
#ifdef _WIN32
    if (!path.empty() && fs::exists(path)) {
        try {
            fs::remove(path);
        } catch (...) {
            // Ignore cleanup errors
        }
    }
#endif
}

bool ModuleLoader::generate_cmake(const ModuleDescriptor& desc, const std::string& build_dir) {
    fs::path module_dir = fs::path(desc.path).parent_path();
    fs::path cmake_path = fs::path(build_dir) / "CMakeLists.txt";

    std::ofstream cmake(cmake_path);
    if (!cmake.is_open()) {
        _last_error = "Cannot create CMakeLists.txt in: " + build_dir;
        return false;
    }

    cmake << "cmake_minimum_required(VERSION 3.16)\n";
    cmake << "project(" << desc.name << " LANGUAGES CXX)\n\n";
    cmake << "set(CMAKE_CXX_STANDARD 20)\n";
    cmake << "set(CMAKE_CXX_STANDARD_REQUIRED ON)\n\n";

    // Collect source files by expanding glob patterns
    cmake << "set(MODULE_SOURCES\n";
    for (const auto& pattern : desc.sources) {
        // Only include .cpp files in sources
        if (pattern.find(".cpp") != std::string::npos || pattern.find("*") != std::string::npos) {
            fs::path pattern_path = module_dir / pattern;
            std::string pattern_str = pattern_path.string();
            // Replace backslashes for CMake
            std::replace(pattern_str.begin(), pattern_str.end(), '\\', '/');

            if (pattern.find("*") != std::string::npos) {
                // Use glob
                cmake << ")\n";
                cmake << "file(GLOB MODULE_SOURCES_GLOB \"" << pattern_str << "\")\n";
                cmake << "list(APPEND MODULE_SOURCES ${MODULE_SOURCES_GLOB})\n";
                cmake << "set(MODULE_SOURCES ${MODULE_SOURCES}\n";
            } else {
                cmake << "    \"" << pattern_str << "\"\n";
            }
        }
    }
    cmake << ")\n\n";

    cmake << "add_library(" << desc.name << " SHARED ${MODULE_SOURCES})\n\n";

    // Include directories
    auto to_cmake_path = [](std::string s) {
        std::replace(s.begin(), s.end(), '\\', '/');
        return s;
    };

    cmake << "target_include_directories(" << desc.name << " PRIVATE\n";
    cmake << "    \"" << to_cmake_path(_core_c) << "\"\n";
    cmake << "    \"" << to_cmake_path(_core_cpp) << "\"\n";
    for (const auto& inc : desc.include_dirs) {
        fs::path inc_path = module_dir / inc;
        cmake << "    \"" << to_cmake_path(inc_path.string()) << "\"\n";
    }
    cmake << ")\n\n";

    // Link libraries
    std::string entity_lib_path = _lib_dir + "/entity_lib";
    std::string termin_core_path = _lib_dir + "/termin_core";
#ifdef _WIN32
    entity_lib_path += ".lib";
    termin_core_path += ".lib";
#else
    entity_lib_path = _lib_dir + "/libentity_lib.so";
    termin_core_path = _lib_dir + "/libtermin_core.so";
#endif
    cmake << "target_link_libraries(" << desc.name << " PRIVATE\n";
    cmake << "    \"" << to_cmake_path(entity_lib_path) << "\"\n";
    cmake << "    \"" << to_cmake_path(termin_core_path) << "\"\n";
    cmake << ")\n\n";

    // Windows export settings
    cmake << "if(WIN32)\n";
    cmake << "    target_compile_definitions(" << desc.name << " PRIVATE MODULE_EXPORTS)\n";
    cmake << "endif()\n";

    cmake.close();
    return true;
}

bool ModuleLoader::run_cmake_build(const std::string& build_dir, const std::string& module_name) {
    _compiler_output.clear();

    // Configure
    std::string config_cmd = "cmake -S \"" + build_dir + "\" -B \"" + build_dir + "/build\" 2>&1";
    FILE* pipe = popen(config_cmd.c_str(), "r");
    if (!pipe) {
        _last_error = "Failed to run cmake configure";
        return false;
    }

    char buffer[256];
    while (fgets(buffer, sizeof(buffer), pipe)) {
        _compiler_output += buffer;
    }
    int config_result = pclose(pipe);
    if (config_result != 0) {
        _last_error = "CMake configure failed";
        return false;
    }

    // Build
    std::string build_cmd = "cmake --build \"" + build_dir + "/build\" --config Release 2>&1";
    pipe = popen(build_cmd.c_str(), "r");
    if (!pipe) {
        _last_error = "Failed to run cmake build";
        return false;
    }

    while (fgets(buffer, sizeof(buffer), pipe)) {
        _compiler_output += buffer;
    }
    int build_result = pclose(pipe);
    if (build_result != 0) {
        _last_error = "CMake build failed";
        return false;
    }

    return true;
}

std::string ModuleLoader::compile_module(const std::string& name) {
    auto it = _modules.find(name);
    if (it == _modules.end()) {
        _last_error = "Module not found: " + name;
        return "";
    }

    const ModuleDescriptor& desc = it->second.descriptor;
    fs::path module_dir = fs::path(desc.path).parent_path();
    fs::path build_dir = module_dir / "build";

    // Create build directory
    try {
        fs::create_directories(build_dir);
    } catch (const std::exception& e) {
        _last_error = "Failed to create build directory: " + std::string(e.what());
        return "";
    }

    emit_event(name, "compiling");

    // Generate CMakeLists.txt
    if (!generate_cmake(desc, build_dir.string())) {
        emit_event(name, "compile_failed");
        return "";
    }

    // Run cmake build
    if (!run_cmake_build(build_dir.string(), desc.name)) {
        emit_event(name, "compile_failed");
        return "";
    }

    // Find output DLL
#ifdef _WIN32
    fs::path dll_path = build_dir / "build" / "Release" / (desc.name + ".dll");
    if (!fs::exists(dll_path)) {
        dll_path = build_dir / "build" / "Debug" / (desc.name + ".dll");
    }
    if (!fs::exists(dll_path)) {
        dll_path = build_dir / "build" / (desc.name + ".dll");
    }
#else
    fs::path dll_path = build_dir / "build" / ("lib" + desc.name + ".so");
#endif

    if (!fs::exists(dll_path)) {
        _last_error = "Compiled DLL not found at expected location";
        emit_event(name, "compile_failed");
        return "";
    }

    emit_event(name, "compiled");
    return dll_path.string();
}

void ModuleLoader::serialize_module_components(const std::string& module_name) {
    // TODO: Implement state serialization
    // This requires iterating all entities and finding components
    // that match the module's registered types
    _serialized_state.clear();
}

void ModuleLoader::restore_module_components(const std::string& module_name) {
    // TODO: Implement state restoration
    // This requires creating new components and deserializing data
    _serialized_state.clear();
}

bool ModuleLoader::load_module(const std::string& module_path) {
    ModuleDescriptor desc;
    if (!parse_module_file(module_path, desc)) {
        return false;
    }

    // Check if already loaded
    if (_modules.count(desc.name)) {
        _last_error = "Module already loaded: " + desc.name;
        return false;
    }

    emit_event(desc.name, "loading");

    // Compile if needed
    fs::path module_dir = fs::path(module_path).parent_path();
    fs::path dll_path;

#ifdef _WIN32
    dll_path = module_dir / "build" / "build" / "Release" / (desc.name + ".dll");
    if (!fs::exists(dll_path)) {
        dll_path = module_dir / "build" / "build" / "Debug" / (desc.name + ".dll");
    }
#else
    dll_path = module_dir / "build" / "build" / ("lib" + desc.name + ".so");
#endif

    bool needs_compile = !fs::exists(dll_path);

    // Check if sources are newer than DLL
    if (!needs_compile && fs::exists(dll_path)) {
        auto dll_time = fs::last_write_time(dll_path);
        for (const auto& src : desc.sources) {
            fs::path src_path = module_dir / src;
            if (fs::exists(src_path) && fs::last_write_time(src_path) > dll_time) {
                tc::Log::info("Source file '%s' is newer than DLL, recompiling...", src.c_str());
                needs_compile = true;
                break;
            }
        }
    }

    if (needs_compile) {
        // Need to compile
        LoadedModule temp;
        temp.name = desc.name;
        temp.descriptor = desc;
        _modules[desc.name] = temp;

        std::string compiled_path = compile_module(desc.name);
        if (compiled_path.empty()) {
            _modules.erase(desc.name);
            return false;
        }
        dll_path = compiled_path;
    }

    // Copy DLL for loading (Windows)
    std::string load_path = copy_dll_for_loading(dll_path.string());
    if (load_path.empty()) {
        return false;
    }

    // Load DLL
    ModuleHandle handle = load_dll(load_path);
    if (!handle) {
        cleanup_temp_dll(load_path);
        emit_event(desc.name, "load_failed");
        return false;
    }

    // Call module_init
    using InitFn = void(*)();
    InitFn init_fn = (InitFn)get_symbol(handle, "module_init");
    if (init_fn) {
        init_fn();
    }

    // Store loaded module info
    LoadedModule mod;
    mod.name = desc.name;
    mod.dll_path = dll_path.string();
    mod.temp_dll_path = load_path;
    mod.handle = handle;
    mod.descriptor = desc;
    mod.registered_components = desc.components;

    _modules[desc.name] = mod;

    emit_event(desc.name, "loaded");
    tc::Log::info("Module loaded: %s", desc.name.c_str());

    return true;
}

bool ModuleLoader::unload_module(const std::string& name) {
    auto it = _modules.find(name);
    if (it == _modules.end()) {
        _last_error = "Module not found: " + name;
        return false;
    }

    emit_event(name, "unloading");

    LoadedModule& mod = it->second;

    // Call module_shutdown
    if (mod.handle) {
        using ShutdownFn = void(*)();
        ShutdownFn shutdown_fn = (ShutdownFn)get_symbol(mod.handle, "module_shutdown");
        if (shutdown_fn) {
            shutdown_fn();
        }
    }

    // Unregister components
    for (const auto& comp : mod.registered_components) {
        ComponentRegistry::instance().unregister(comp);
        tc::InspectRegistry::instance().unregister_type(comp);
    }

    // Unload DLL
    unload_dll(mod.handle);

    // Cleanup temp DLL
    cleanup_temp_dll(mod.temp_dll_path);

    _modules.erase(it);

    emit_event(name, "unloaded");
    tc::Log::info("Module unloaded: %s", name.c_str());

    return true;
}

bool ModuleLoader::reload_module(const std::string& name) {
    auto it = _modules.find(name);
    if (it == _modules.end()) {
        _last_error = "Module not found: " + name;
        return false;
    }

    emit_event(name, "reloading");

    // Store descriptor before unload
    ModuleDescriptor desc = it->second.descriptor;

    // Serialize component state
    serialize_module_components(name);

    // Unload
    if (!unload_module(name)) {
        return false;
    }

    // Re-create entry for compilation
    LoadedModule temp;
    temp.name = desc.name;
    temp.descriptor = desc;
    _modules[desc.name] = temp;

    // Compile
    std::string dll_path = compile_module(name);
    if (dll_path.empty()) {
        _modules.erase(name);
        return false;
    }

    // Remove temp entry
    _modules.erase(name);

    // Load
    if (!load_module(desc.path)) {
        return false;
    }

    // Restore component state
    restore_module_components(name);

    emit_event(name, "reloaded");
    tc::Log::info("Module reloaded: %s", name.c_str());

    return true;
}

std::vector<std::string> ModuleLoader::list_modules() const {
    std::vector<std::string> result;
    result.reserve(_modules.size());
    for (const auto& [name, _] : _modules) {
        result.push_back(name);
    }
    return result;
}

const LoadedModule* ModuleLoader::get_module(const std::string& name) const {
    auto it = _modules.find(name);
    return it != _modules.end() ? &it->second : nullptr;
}

bool ModuleLoader::is_loaded(const std::string& name) const {
    return _modules.count(name) > 0;
}

void ModuleLoader::set_event_callback(ModuleEventCallback callback) {
    _event_callback = std::move(callback);
}

void ModuleLoader::emit_event(const std::string& module_name, const std::string& event) {
    if (_event_callback) {
        _event_callback(module_name, event);
    }
}

void ModuleLoader::set_engine_paths(
    const std::string& core_c,
    const std::string& core_cpp,
    const std::string& lib_dir
) {
    _core_c = core_c;
    _core_cpp = core_cpp;
    _lib_dir = lib_dir;
}

} // namespace termin
