#include "termin_modules/module_cpp_backend.hpp"
#include "termin_modules/text_encoding.hpp"

#include <tcbase/tc_log.hpp>

#include <cstdio>
#include <cstdlib>
#include <exception>
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

std::string shell_quote(const std::filesystem::path& path) {
    const std::string text = path.string();
#ifdef _WIN32
    std::string result = "\"";
    for (char ch : text) {
        if (ch == '"') {
            result += "\\\"";
        } else {
            result += ch;
        }
    }
    result += "\"";
    return result;
#else
    std::string result = "'";
    for (char ch : text) {
        if (ch == '\'') {
            result += "'\\''";
        } else {
            result += ch;
        }
    }
    result += "'";
    return result;
#endif
}

std::filesystem::path native_validator_path(const ModuleEnvironment& environment) {
    if (environment.sdk_prefix.empty()) {
        return {};
    }

#ifdef _WIN32
    return environment.sdk_prefix / "bin" / "termin_module_native_validator.exe";
#else
    return environment.sdk_prefix / "bin" / "termin_module_native_validator";
#endif
}

bool run_shell_command_capture(
    const std::string& command,
    const std::filesystem::path& working_dir,
    std::string& output,
    std::string& error
) {
    output.clear();
    error.clear();

    const std::filesystem::path previous_dir = std::filesystem::current_path();
    try {
        if (!working_dir.empty()) {
            std::filesystem::current_path(working_dir);
        }
    } catch (const std::exception& e) {
        error = "Failed to change working directory: ";
        error += e.what();
        return false;
    }

    std::string popen_command = command;
#ifdef _WIN32
    // _popen delegates to cmd.exe /c. If the command itself starts with a
    // quoted executable path and has quoted arguments, cmd can misparse the
    // line before the helper process starts. The extra outer quotes produce
    // the canonical cmd form: cmd /c ""tool.exe" "arg" 2>&1".
    if (!popen_command.empty() && popen_command.front() == '"') {
        popen_command = "\"" + popen_command + "\"";
    }
#endif

    FILE* pipe = popen(popen_command.c_str(), "r");
    if (pipe == nullptr) {
        std::filesystem::current_path(previous_dir);
        error = "Failed to start command";
        return false;
    }

    char buffer[512];
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        output += sanitize_external_text(buffer);
    }

    const int result = pclose(pipe);
    std::filesystem::current_path(previous_dir);

    if (result != 0) {
        std::ostringstream ss;
        ss << "Command failed with exit code " << result;
        error = ss.str();
        return false;
    }

    return true;
}

std::string relocation_diagnostics_for_linux(const std::filesystem::path& artifact_path) {
#ifdef _WIN32
    (void)artifact_path;
    return {};
#else
    std::string output;
    std::string error;
    const std::string command = "ldd -r " + shell_quote(artifact_path) + " 2>&1 | c++filt";
    if (!run_shell_command_capture(command, artifact_path.parent_path(), output, error)) {
        if (output.empty()) {
            return "ldd -r diagnostics unavailable: " + error + "\n";
        }
    }

    std::istringstream lines(output);
    std::ostringstream filtered;
    std::string line;
    while (std::getline(lines, line)) {
        if (line.find("undefined symbol:") != std::string::npos ||
            line.find("symbol lookup error:") != std::string::npos ||
            line.find("not found") != std::string::npos) {
            filtered << line << '\n';
        }
    }

    std::string result = filtered.str();
    if (result.empty() && !output.empty()) {
        result = output;
    }
    return result;
#endif
}

bool validate_native_artifact(
    ModuleRecord& record,
    const ModuleEnvironment& environment,
    const std::filesystem::path& artifact_path
) {
    const std::filesystem::path validator = native_validator_path(environment);
    if (validator.empty()) {
        return true;
    }

    if (!std::filesystem::exists(validator)) {
        record.error_message = "Native module validator not found: " + validator.string();
        return false;
    }

    std::string output;
    std::string error;
    const std::string command = shell_quote(validator) + " " + shell_quote(artifact_path) + " 2>&1";
    if (run_shell_command_capture(command, artifact_path.parent_path(), output, error)) {
        return true;
    }

    std::ostringstream message;
    message << "Native artifact validation failed for " << artifact_path.string();
    if (!output.empty()) {
        message << ": " << output;
    } else if (!error.empty()) {
        message << ": " << error;
    }
    record.error_message = message.str();

    const std::string relocation_diagnostics = relocation_diagnostics_for_linux(artifact_path);
    if (!relocation_diagnostics.empty()) {
        record.diagnostics += "\n[Native artifact relocation diagnostics]\n";
        record.diagnostics += relocation_diagnostics;
    }
    return false;
}

void* load_shared_library(const std::filesystem::path& path, std::string& error) {
#ifdef _WIN32
    std::filesystem::path load_path = std::filesystem::absolute(path);
    load_path.make_preferred();
    const std::string load_path_string = load_path.string();
    HMODULE handle = LoadLibraryExA(
        load_path_string.c_str(),
        nullptr,
        LOAD_WITH_ALTERED_SEARCH_PATH
    );
    if (handle == nullptr) {
        const DWORD error_code = GetLastError();
        std::ostringstream ss;
        ss << "LoadLibraryEx failed for " << load_path_string
           << " with error code " << error_code;
        error = ss.str();
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

bool CppModuleBackend::needs_rebuild(
    const ModuleRecord& record,
    const ModuleEnvironment& environment
) {
    (void)environment;

    const auto config = std::dynamic_pointer_cast<CppModuleConfig>(record.spec.config);
    if (!config) return false;
    if (config->artifact_path.empty()) return true;
    if (!std::filesystem::exists(config->artifact_path)) return true;

    auto artifact_time = std::filesystem::last_write_time(config->artifact_path);

    // Scan module directory for source files newer than artifact
    std::filesystem::path module_dir = record.spec.descriptor_path.parent_path();
    if (!std::filesystem::exists(module_dir)) return true;

    try {
        for (auto it = std::filesystem::recursive_directory_iterator(module_dir);
             it != std::filesystem::recursive_directory_iterator(); ++it) {
            const auto& entry = *it;

            // Skip build directories
            if (entry.is_directory()) {
                std::string dirname = entry.path().filename().string();
                if (dirname == "build" || dirname == "__pycache__" ||
                    (!dirname.empty() && dirname[0] == '.')) {
                    it.disable_recursion_pending();
                    continue;
                }
                continue;
            }

            if (!entry.is_regular_file()) continue;

            if (entry.last_write_time() > artifact_time) {
                return true;
            }
        }
    } catch (const std::exception& e) {
        tc::Log::warn(e, "CppModuleBackend::needs_rebuild: filesystem iteration failed, assuming rebuild needed");
        return true;
    } catch (...) {
        tc::Log::warn("CppModuleBackend::needs_rebuild: unknown error during filesystem iteration, assuming rebuild needed");
        return true;
    }

    return false;
}

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

    if (!validate_native_artifact(record, environment, config->artifact_path)) {
        return false;
    }

    // Copy artifact to a unique path to avoid dlopen cache
    static int load_counter = 0;
    std::filesystem::path load_path = config->artifact_path;
    load_path += ".loaded." + std::to_string(++load_counter);
    try {
        std::filesystem::copy_file(
            config->artifact_path, load_path,
            std::filesystem::copy_options::overwrite_existing
        );
    } catch (const std::exception& e) {
        record.error_message = "Failed to copy artifact for loading: ";
        record.error_message += e.what();
        return false;
    }

    std::string error;
    void* native_handle = load_shared_library(load_path, error);
    if (native_handle == nullptr) {
        record.error_message = "Failed to load shared library: " + error;
        return false;
    }

    InitFn init_fn = reinterpret_cast<InitFn>(resolve_symbol(native_handle, "module_init"));
    if (init_fn != nullptr) {
        bool init_scope_started = false;
        auto end_init_scope = [&]() {
            if (init_scope_started && environment.after_cpp_module_init) {
                environment.after_cpp_module_init(record);
            }
            init_scope_started = false;
        };

        try {
            if (environment.before_cpp_module_init) {
                init_scope_started = true;
                environment.before_cpp_module_init(record);
            }
            init_fn();
            end_init_scope();
        } catch (const std::exception& e) {
            end_init_scope();
            unload_shared_library(native_handle);
            record.error_message = "module_init failed: ";
            record.error_message += e.what();
            return false;
        } catch (...) {
            end_init_scope();
            unload_shared_library(native_handle);
            record.error_message = "module_init failed with unknown exception";
            return false;
        }
    }

    auto handle = std::make_shared<CppModuleHandle>();
    handle->artifact_path = config->artifact_path;
    handle->loaded_path = load_path;
    handle->native_handle = native_handle;
    record.handle = handle;
    return true;
}

bool CppModuleBackend::unload(
    ModuleRecord& record,
    const ModuleEnvironment& environment
) {
    if (!begin_unload(record, environment)) {
        return false;
    }
    return finish_unload(record, environment);
}

bool CppModuleBackend::begin_unload(
    ModuleRecord& record,
    const ModuleEnvironment& environment
) {
    (void)environment;

    auto handle = std::dynamic_pointer_cast<CppModuleHandle>(record.handle);
    if (!handle) {
        return true;
    }
    if (handle->shutdown_called) {
        return true;
    }

    InitFn shutdown_fn = reinterpret_cast<InitFn>(resolve_symbol(handle->native_handle, "module_shutdown"));
    if (shutdown_fn != nullptr) {
        shutdown_fn();
    }
    handle->shutdown_called = true;
    return true;
}

bool CppModuleBackend::finish_unload(
    ModuleRecord& record,
    const ModuleEnvironment& environment
) {
    (void)environment;

    auto handle = std::dynamic_pointer_cast<CppModuleHandle>(record.handle);
    if (!handle) {
        return true;
    }

    unload_shared_library(handle->native_handle);
    handle->native_handle = nullptr;
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
        const std::string sanitized = sanitize_external_text(buffer);
        output += sanitized;
        if (_output_callback) {
            // Strip trailing newline for callback
            std::string line(sanitized);
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
