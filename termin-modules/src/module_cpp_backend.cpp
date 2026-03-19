#include "termin_modules/module_cpp_backend.hpp"

#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <sstream>

#ifdef _WIN32
    #ifndef NOMINMAX
        #define NOMINMAX
    #endif
    #ifndef WIN32_LEAN_AND_MEAN
        #define WIN32_LEAN_AND_MEAN
    #endif
    #include <windows.h>
    #define popen _popen
    #define pclose _pclose
#else
    #include <dlfcn.h>
#endif

namespace termin_modules {
namespace {

using InitFn = void (*)();

void* load_shared_library(const std::filesystem::path& path, std::string& error) {
#ifdef _WIN32
    HMODULE handle = LoadLibraryA(path.string().c_str());
    if (handle == nullptr) {
        error = "LoadLibrary failed";
        return nullptr;
    }
    return reinterpret_cast<void*>(handle);
#else
    void* handle = dlopen(path.string().c_str(), RTLD_NOW | RTLD_LOCAL);
    if (handle == nullptr) {
        error = dlerror();
        return nullptr;
    }
    return handle;
#endif
}

void unload_shared_library(void* handle) {
    if (handle == nullptr) {
        return;
    }

#ifdef _WIN32
    FreeLibrary(reinterpret_cast<HMODULE>(handle));
#else
    dlclose(handle);
#endif
}

void* resolve_symbol(void* handle, const char* name) {
    if (handle == nullptr) {
        return nullptr;
    }

#ifdef _WIN32
    return reinterpret_cast<void*>(GetProcAddress(reinterpret_cast<HMODULE>(handle), name));
#else
    return dlsym(handle, name);
#endif
}

} // namespace

void CppModuleBackend::set_output_callback(BuildOutputCallback callback) {
    _output_callback = std::move(callback);
}

bool CppModuleBackend::build(
    ModuleRecord& record,
    const ModuleEnvironment& environment
) {
    const auto config = std::dynamic_pointer_cast<CppModuleConfig>(record.spec.config);
    if (!config) {
        record.error_message = "Invalid C++ module config";
        return false;
    }

    record.diagnostics.clear();
    record.error_message.clear();

    if (config->build_command.empty()) {
        return true;
    }

    std::string output;
    std::string error;
    if (!run_build_command(
            record.spec.id,
            config->build_command,
            record.spec.descriptor_path.parent_path(),
            environment,
            output,
            error
        )) {
        record.diagnostics = output;
        record.error_message = error;
        return false;
    }
    record.diagnostics = output;
    return true;
}

bool CppModuleBackend::load(
    ModuleRecord& record,
    const ModuleEnvironment& environment
) {
    if (!build(record, environment)) {
        return false;
    }

    const auto config = std::dynamic_pointer_cast<CppModuleConfig>(record.spec.config);
    if (!config) {
        record.error_message = "Invalid C++ module config";
        return false;
    }

    if (!std::filesystem::exists(config->artifact_path)) {
        record.error_message = "Artifact not found: " + config->artifact_path.string();
        return false;
    }

    std::string error;
    void* native_handle = load_shared_library(config->artifact_path, error);
    if (native_handle == nullptr) {
        record.error_message = "Failed to load shared library: " + error;
        return false;
    }

    InitFn init_fn = reinterpret_cast<InitFn>(resolve_symbol(native_handle, "module_init"));
    if (init_fn != nullptr) {
        init_fn();
    }

    auto handle = std::make_shared<CppModuleHandle>();
    handle->artifact_path = config->artifact_path;
    handle->loaded_path = config->artifact_path;
    handle->native_handle = native_handle;
    record.handle = handle;
    return true;
}

bool CppModuleBackend::unload(
    ModuleRecord& record,
    const ModuleEnvironment& environment
) {
    (void)environment;

    auto handle = std::dynamic_pointer_cast<CppModuleHandle>(record.handle);
    if (!handle) {
        return true;
    }

    InitFn shutdown_fn = reinterpret_cast<InitFn>(resolve_symbol(handle->native_handle, "module_shutdown"));
    if (shutdown_fn != nullptr) {
        shutdown_fn();
    }

    unload_shared_library(handle->native_handle);
    return true;
}

bool CppModuleBackend::clean(
    ModuleRecord& record,
    const ModuleEnvironment& environment
) {
    const auto config = std::dynamic_pointer_cast<CppModuleConfig>(record.spec.config);
    if (!config) {
        record.error_message = "Invalid C++ module config";
        return false;
    }

    if (config->clean_command.empty()) {
        record.error_message = "No clean command configured";
        return false;
    }

    record.diagnostics.clear();
    record.error_message.clear();

    std::string output;
    std::string error;
    if (!run_build_command(
            record.spec.id,
            config->clean_command,
            record.spec.descriptor_path.parent_path(),
            environment,
            output,
            error
        )) {
        record.diagnostics = output;
        record.error_message = error;
        return false;
    }
    record.diagnostics = output;
    return true;
}

bool CppModuleBackend::run_build_command(
    const std::string& module_id,
    const std::string& command,
    const std::filesystem::path& working_dir,
    const ModuleEnvironment& environment,
    std::string& output,
    std::string& error
) const {
    output.clear();
    error.clear();

    const std::filesystem::path previous_dir = std::filesystem::current_path();
    try {
        std::filesystem::current_path(working_dir);
    } catch (const std::exception& e) {
        error = "Failed to change working directory: ";
        error += e.what();
        return false;
    }

    std::string full_command;
#ifdef _WIN32
    const std::filesystem::path prefix_path =
        !environment.cmake_prefix_path.empty() ? environment.cmake_prefix_path : environment.sdk_prefix;
    if (!prefix_path.empty()) {
        full_command += "set CMAKE_PREFIX_PATH=" + prefix_path.string() + "&& ";
    }
#else
    const std::filesystem::path prefix_path =
        !environment.cmake_prefix_path.empty() ? environment.cmake_prefix_path : environment.sdk_prefix;
    if (!prefix_path.empty()) {
        full_command += "CMAKE_PREFIX_PATH=\"" + prefix_path.string() + "\" ";
    }
#endif
    full_command += command;
    full_command += " 2>&1";

    FILE* pipe = popen(full_command.c_str(), "r");
    if (pipe == nullptr) {
        std::filesystem::current_path(previous_dir);
        error = "Failed to start build command";
        return false;
    }

    char buffer[512];
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        output += buffer;
        if (_output_callback) {
            // Strip trailing newline for callback
            std::string line(buffer);
            while (!line.empty() && (line.back() == '\n' || line.back() == '\r')) {
                line.pop_back();
            }
            if (!line.empty()) {
                _output_callback(module_id, line);
            }
        }
    }

    const int result = pclose(pipe);
    std::filesystem::current_path(previous_dir);

    if (result != 0) {
        std::ostringstream ss;
        ss << "Build command failed with exit code " << result;
        error = ss.str();
        return false;
    }

    return true;
}

} // namespace termin_modules
