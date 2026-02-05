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
#include "tc_inspect_cpp.hpp"
#include <tc_log.hpp>
#include <tc_version.h>

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

    // Parse name (required)
    if (tr.contains("name") && tr["name"].is_string()) {
        out.name = tr["name"].as_string();
    } else {
        _last_error = "Module file missing 'name' field";
        return false;
    }

    // Parse build section (required)
    if (tr.contains("build") && tr["build"].is_dict()) {
        const auto& build = tr["build"];

        if (build.contains("command") && build["command"].is_string()) {
            out.build_command = build["command"].as_string();
        } else {
            _last_error = "Module file missing 'build.command' field";
            return false;
        }

        if (build.contains("output") && build["output"].is_string()) {
            out.output_pattern = build["output"].as_string();
        } else {
            _last_error = "Module file missing 'build.output' field";
            return false;
        }
    } else {
        _last_error = "Module file missing 'build' section";
        return false;
    }

    // Parse components (optional)
    if (tr.contains("components") && tr["components"].is_list()) {
        for (const auto& comp : tr["components"].as_list()) {
            if (comp.is_string()) {
                out.components.push_back(comp.as_string());
            }
        }
    }

    return true;
}

std::string ModuleLoader::get_state_path(const std::string& module_path) {
    // module.module -> module.module.state
    return module_path + ".state";
}

bool ModuleLoader::read_module_state(const std::string& module_path, ModuleState& out) {
    std::string state_path = get_state_path(module_path);

    std::ifstream file(state_path);
    if (!file.is_open()) {
        // No state file - not built yet
        out.built_version = 0;
        return true;
    }

    std::stringstream buffer;
    buffer << file.rdbuf();
    std::string content = buffer.str();

    nos::trent tr;
    try {
        tr = nos::yaml::parse(content);
    } catch (const std::exception& e) {
        tc::Log::warn("Failed to parse module state file: %s", e.what());
        out.built_version = 0;
        return true;
    }

    if (tr.contains("built_version") && tr["built_version"].is_numer()) {
        out.built_version = (int)tr["built_version"].as_integer();
    } else {
        out.built_version = 0;
    }

    return true;
}

bool ModuleLoader::write_module_state(const std::string& module_path, const ModuleState& state) {
    std::string state_path = get_state_path(module_path);

    std::ofstream out(state_path);
    if (!out.is_open()) {
        tc::Log::error("Cannot write module state file: %s", state_path.c_str());
        return false;
    }

    out << "{\n";
    out << "    \"built_version\": " << state.built_version << "\n";
    out << "}\n";
    out.close();

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

std::string ModuleLoader::expand_output_pattern(const std::string& pattern, const std::string& name) {
    std::string result = pattern;

    // Replace ${name} with module name
    size_t pos = 0;
    while ((pos = result.find("${name}", pos)) != std::string::npos) {
        result.replace(pos, 7, name);
        pos += name.length();
    }

#ifndef _WIN32
    // On Linux/macOS: convert Windows-style paths to Unix-style
    // "build/Release/${name}.dll" -> "build/lib${name}.so"

    // Replace backslashes with forward slashes
    for (char& c : result) {
        if (c == '\\') c = '/';
    }

    // Remove /Release/ or /Debug/ from path (CMake single-config on Unix)
    pos = result.find("/Release/");
    if (pos != std::string::npos) {
        result.erase(pos, 8);  // Remove "/Release" but keep trailing "/"
    }
    pos = result.find("/Debug/");
    if (pos != std::string::npos) {
        result.erase(pos, 6);  // Remove "/Debug" but keep trailing "/"
    }

    // Replace .dll with .so
    pos = result.rfind(".dll");
    if (pos != std::string::npos && pos == result.length() - 4) {
        result.replace(pos, 4, ".so");
    }

    // Add lib prefix if not present
    size_t last_slash = result.rfind('/');
    size_t name_start = (last_slash != std::string::npos) ? last_slash + 1 : 0;
    if (result.substr(name_start, 3) != "lib") {
        result.insert(name_start, "lib");
    }
#endif

    return result;
}

bool ModuleLoader::run_build_command(const std::string& command, const std::string& working_dir) {
    _compiler_output.clear();

    // Save current directory
    fs::path old_cwd = fs::current_path();

    // Change to working directory
    try {
        fs::current_path(working_dir);
    } catch (const std::exception& e) {
        _last_error = "Failed to change to module directory: " + std::string(e.what());
        return false;
    }

    // Build command with CMAKE_PREFIX_PATH for find_package(termin)
    std::string full_cmd = command;

    // Derive install prefix from lib_dir (lib_dir is PREFIX/lib, we need PREFIX)
    if (!_lib_dir.empty()) {
        fs::path lib_path(_lib_dir);
        fs::path prefix = lib_path.parent_path();
        if (fs::exists(prefix / "lib" / "cmake" / "termin")) {
            // Inject CMAKE_PREFIX_PATH into cmake commands
            std::string prefix_arg = "-DCMAKE_PREFIX_PATH=" + prefix.string();

            // Find "cmake -B" and insert prefix path after it
            size_t pos = full_cmd.find("cmake -B");
            if (pos != std::string::npos) {
                // Find the end of "-B <dir>" part
                size_t space_after_B = full_cmd.find(' ', pos + 8);
                if (space_after_B != std::string::npos) {
                    size_t next_space = full_cmd.find(' ', space_after_B + 1);
                    if (next_space == std::string::npos) {
                        next_space = full_cmd.length();
                    }
                    full_cmd.insert(next_space, " " + prefix_arg);
                }
            }
        }
    }

    full_cmd += " 2>&1";
    FILE* pipe = popen(full_cmd.c_str(), "r");
    if (!pipe) {
        fs::current_path(old_cwd);
        _last_error = "Failed to run build command";
        return false;
    }

    char buffer[256];
    while (fgets(buffer, sizeof(buffer), pipe)) {
        _compiler_output += buffer;
    }
    int result = pclose(pipe);

    // Restore directory
    fs::current_path(old_cwd);

    if (result != 0) {
        _last_error = "Build command failed with exit code: " + std::to_string(result);
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

    emit_event(name, "compiling");

    // Run build command in module directory
    if (!run_build_command(desc.build_command, module_dir.string())) {
        emit_event(name, "compile_failed");
        return "";
    }

    // Find output DLL using pattern
    std::string output_relative = expand_output_pattern(desc.output_pattern, desc.name);
    fs::path dll_path = module_dir / output_relative;

    if (!fs::exists(dll_path)) {
        _last_error = "Compiled DLL not found at: " + dll_path.string();
        emit_event(name, "compile_failed");
        return "";
    }

    // Update state file
    ModuleState new_state;
    new_state.built_version = TC_VERSION;
    write_module_state(desc.path, new_state);
    it->second.state = new_state;

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

    // Find DLL using output pattern
    fs::path module_dir = fs::path(module_path).parent_path();
    std::string output_relative = expand_output_pattern(desc.output_pattern, desc.name);
    fs::path dll_path = module_dir / output_relative;

    bool needs_compile = !fs::exists(dll_path);

    // Check if module was built with different engine version
    ModuleState state;
    read_module_state(module_path, state);
    if (!needs_compile && state.built_version != TC_VERSION) {
        needs_compile = true;
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
        state.built_version = TC_VERSION;  // Update state after successful compilation
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
    mod.state = state;
    mod.registered_components = desc.components;

    _modules[desc.name] = mod;

    emit_event(desc.name, "loaded");

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
