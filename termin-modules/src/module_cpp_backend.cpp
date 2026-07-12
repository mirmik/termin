#include "termin_modules/module_cpp_backend.hpp"
#include "termin_modules/text_encoding.hpp"
#include "termin_modules/native_module_validation.hpp"

#include <tcbase/tc_log.hpp>

#include <algorithm>
#include <cerrno>
#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <chrono>
#include <exception>
#include <filesystem>
#include <optional>
#include <sstream>
#include <vector>

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
    #include <csignal>
    #include <dlfcn.h>
    #include <unistd.h>
#endif

namespace termin_modules {
namespace {

constexpr auto kAbandonedShadowAge = std::chrono::hours(24);

void native_module_host_log(void*, int level, const char* message) {
    const char* text = message ? message : "";
    switch (level) {
        case TERMIN_NATIVE_MODULE_LOG_DEBUG: tc::Log::debug("[NativeModule] %s", text); break;
        case TERMIN_NATIVE_MODULE_LOG_INFO: tc::Log::info("[NativeModule] %s", text); break;
        case TERMIN_NATIVE_MODULE_LOG_WARN: tc::Log::warn("[NativeModule] %s", text); break;
        default: tc::Log::error("[NativeModule] %s", text); break;
    }
}

std::string native_module_error_message(
    int32_t status,
    const char* phase,
    const char* buffer
) {
    std::string result = std::string(phase) + " failed with status " +
        std::to_string(status);
    if (buffer && buffer[0]) result += ": " + std::string(buffer);
    return result;
}

uint64_t process_id() {
#ifdef _WIN32
    return static_cast<uint64_t>(GetCurrentProcessId());
#else
    return static_cast<uint64_t>(getpid());
#endif
}

bool process_is_alive(uint64_t pid) {
#ifdef _WIN32
    HANDLE process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, static_cast<DWORD>(pid));
    if (process == nullptr) {
        return false;
    }
    DWORD exit_code = 0;
    const bool alive = GetExitCodeProcess(process, &exit_code) != 0 && exit_code == STILL_ACTIVE;
    CloseHandle(process);
    return alive;
#else
    if (kill(static_cast<pid_t>(pid), 0) == 0) {
        return true;
    }
    return errno == EPERM;
#endif
}

std::optional<uint64_t> shadow_session_process_id(const std::filesystem::path& path) {
    const std::string name = path.filename().string();
    constexpr const char* prefix = "session-";
    if (!name.starts_with(prefix)) {
        return std::nullopt;
    }
    const size_t begin = std::char_traits<char>::length(prefix);
    const size_t end = name.find('-', begin);
    if (end == std::string::npos) {
        return std::nullopt;
    }
    try {
        return std::stoull(name.substr(begin, end - begin));
    } catch (...) {
        return std::nullopt;
    }
}

bool is_dynamic_library_file(const std::filesystem::path& path) {
    std::string name = path.filename().string();
#ifdef _WIN32
    for (char& ch : name) {
        ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    }
    return path.extension() == ".dll" || name.ends_with(".dll");
#elif defined(__APPLE__)
    return name.ends_with(".dylib");
#else
    const size_t so = name.find(".so");
    return so != std::string::npos && (so + 3 == name.size() || name[so + 3] == '.');
#endif
}

void prune_abandoned_shadow_sessions(const std::filesystem::path& base_dir) {
    std::error_code ec;
    std::filesystem::directory_iterator it(base_dir, ec);
    if (ec) {
        tc::Log::error(
            "CppModuleBackend: failed to enumerate native shadow root '%s': %s",
            base_dir.string().c_str(),
            ec.message().c_str()
        );
        return;
    }

    const auto now = std::filesystem::file_time_type::clock::now();
    for (const auto& entry : it) {
        if (!entry.is_directory(ec) || ec) {
            ec.clear();
            continue;
        }

        const std::optional<uint64_t> owner_pid = shadow_session_process_id(entry.path());
        if (!owner_pid.has_value() || process_is_alive(*owner_pid)) {
            continue;
        }

        const auto modified = entry.last_write_time(ec);
        if (ec) {
            tc::Log::warn(
                "CppModuleBackend: cannot inspect abandoned shadow session '%s': %s",
                entry.path().string().c_str(),
                ec.message().c_str()
            );
            ec.clear();
            continue;
        }
        if (now - modified < kAbandonedShadowAge) {
            continue;
        }

        std::filesystem::remove_all(entry.path(), ec);
        if (ec) {
            tc::Log::error(
                "CppModuleBackend: failed to remove abandoned shadow session '%s': %s",
                entry.path().string().c_str(),
                ec.message().c_str()
            );
            ec.clear();
        } else {
            tc::Log::info(
                "CppModuleBackend: removed abandoned native shadow session '%s'",
                entry.path().string().c_str()
            );
        }
    }
}

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

std::filesystem::path native_validator_path(
    const ModuleEnvironment& environment,
    const std::filesystem::path& artifact_path
) {
    if (environment.sdk_prefix.empty()) {
        return {};
    }

#ifdef _WIN32
    const std::filesystem::path installed =
        environment.sdk_prefix / "bin" / "termin_module_native_validator.exe";
    if (std::filesystem::exists(installed)) {
        return installed;
    }

    // CMake multi-config build trees place runtime tools in bin/<config>.
    // Accept that layout only when it resolves unambiguously; installed SDKs
    // continue to use the canonical flat bin directory above.
    std::vector<std::filesystem::path> multi_config_candidates;
    std::error_code iteration_error;
    const std::filesystem::path bin_dir = environment.sdk_prefix / "bin";
    for (std::filesystem::directory_iterator it(bin_dir, iteration_error), end;
         !iteration_error && it != end;
         it.increment(iteration_error)) {
        if (!it->is_directory()) {
            continue;
        }
        const std::filesystem::path candidate =
            it->path() / "termin_module_native_validator.exe";
        if (std::filesystem::is_regular_file(candidate)) {
            multi_config_candidates.push_back(candidate);
        }
    }
    if (multi_config_candidates.size() == 1) {
        return multi_config_candidates.front();
    }
    return artifact_path.parent_path() / "termin_module_native_validator.exe";
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
    const std::filesystem::path validator =
        native_validator_path(environment, artifact_path);
    if (validator.empty()) {
        return true;
    }

    if (!std::filesystem::exists(validator)) {
        record.error_message = "Native module validator not found: " + validator.string();
        return false;
    }

    std::string output;
    std::string error;
    const std::string command = shell_quote(validator) + " " +
        shell_quote(artifact_path) + " " +
        shell_quote(std::filesystem::path(record.spec.id)) + " 2>&1";
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

void* load_shared_library(
    const std::filesystem::path& path,
    const std::filesystem::path& artifact_dir,
    const std::filesystem::path& sdk_bin_dir,
    std::string& error
) {
#ifdef _WIN32
    std::filesystem::path load_path = std::filesystem::absolute(path);
    load_path.make_preferred();
    std::vector<DLL_DIRECTORY_COOKIE> dependency_cookies;
    for (const auto& directory : {artifact_dir, sdk_bin_dir}) {
        if (directory.empty()) {
            continue;
        }
        std::filesystem::path dependency_path = std::filesystem::absolute(directory);
        dependency_path.make_preferred();
        DLL_DIRECTORY_COOKIE cookie = AddDllDirectory(dependency_path.c_str());
        if (cookie == nullptr) {
            const DWORD error_code = GetLastError();
            for (DLL_DIRECTORY_COOKIE added_cookie : dependency_cookies) {
                RemoveDllDirectory(added_cookie);
            }
            std::ostringstream ss;
            ss << "AddDllDirectory failed for " << dependency_path.string()
               << " with error code " << error_code;
            error = ss.str();
            return nullptr;
        }
        dependency_cookies.push_back(cookie);
    }
    HMODULE handle = LoadLibraryExW(
        load_path.c_str(),
        nullptr,
        LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR |
            LOAD_LIBRARY_SEARCH_DEFAULT_DIRS |
            LOAD_LIBRARY_SEARCH_USER_DIRS
    );
    const DWORD load_error_code = handle == nullptr ? GetLastError() : ERROR_SUCCESS;
    for (DLL_DIRECTORY_COOKIE cookie : dependency_cookies) {
        RemoveDllDirectory(cookie);
    }
    if (handle == nullptr) {
        std::ostringstream ss;
        ss << "LoadLibraryEx failed for " << load_path.string()
           << " with error code " << load_error_code;
        error = ss.str();
        return nullptr;
    }
    return reinterpret_cast<void*>(handle);
#else
    (void)artifact_dir;
    (void)sdk_bin_dir;
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

CppModuleBackend::~CppModuleBackend() noexcept {
    if (_shadow_session_dir.empty()) {
        return;
    }

    std::error_code ec;
    const bool removed = std::filesystem::remove(_shadow_session_dir, ec);
    if (ec) {
        tc::Log::error(
            "CppModuleBackend: failed to remove native shadow session directory '%s': %s",
            _shadow_session_dir.string().c_str(),
            ec.message().c_str()
        );
        return;
    }
    const bool still_exists = std::filesystem::exists(_shadow_session_dir, ec);
    if (ec) {
        tc::Log::error(
            "CppModuleBackend: failed to inspect native shadow session directory '%s': %s",
            _shadow_session_dir.string().c_str(),
            ec.message().c_str()
        );
        return;
    }
    if (!removed && still_exists) {
        tc::Log::error(
            "CppModuleBackend: native shadow session directory is not empty at destruction: '%s'",
            _shadow_session_dir.string().c_str()
        );
        return;
    }

    std::filesystem::remove(_shadow_base_dir, ec);
}

bool CppModuleBackend::ensure_shadow_session(
    const ModuleEnvironment& environment,
    std::string& error
) {
    std::lock_guard<std::mutex> lock(_shadow_mutex);
    if (!_shadow_session_dir.empty()) {
        return true;
    }

    std::error_code ec;
    _shadow_base_dir = environment.native_shadow_root.empty()
        ? std::filesystem::temp_directory_path(ec) / "termin-modules-shadow"
        : environment.native_shadow_root;
    if (ec) {
        error = "Failed to resolve native shadow root: " + ec.message();
        return false;
    }

    std::filesystem::create_directories(_shadow_base_dir, ec);
    if (ec) {
        error = "Failed to create native shadow root '" + _shadow_base_dir.string() + "': " + ec.message();
        return false;
    }
    prune_abandoned_shadow_sessions(_shadow_base_dir);

    static std::atomic<uint64_t> session_counter{0};
    const auto now = std::chrono::steady_clock::now().time_since_epoch().count();
    for (size_t attempt = 0; attempt < 100; ++attempt) {
        const uint64_t sequence = session_counter.fetch_add(1, std::memory_order_relaxed);
        const std::string name =
            "session-" + std::to_string(process_id()) + "-" +
            std::to_string(now) + "-" + std::to_string(sequence);
        const std::filesystem::path candidate = _shadow_base_dir / name;
        if (std::filesystem::create_directory(candidate, ec)) {
            _shadow_session_dir = candidate;
            return true;
        }
        if (ec) {
            error = "Failed to create native shadow session '" + candidate.string() + "': " + ec.message();
            return false;
        }
    }

    error = "Failed to allocate a collision-free native shadow session under '" +
        _shadow_base_dir.string() + "'";
    return false;
}

std::filesystem::path CppModuleBackend::next_shadow_path(
    const std::filesystem::path& artifact_path,
    const ModuleEnvironment& environment,
    std::string& error
) {
    if (!ensure_shadow_session(environment, error)) {
        return {};
    }

    const uint64_t sequence = _shadow_counter.fetch_add(1, std::memory_order_relaxed);
    const std::filesystem::path load_dir = _shadow_session_dir / ("load-" + std::to_string(sequence));
    std::error_code ec;
    if (!std::filesystem::create_directory(load_dir, ec)) {
        error = "Failed to create native shadow load directory '" + load_dir.string() + "': " +
            (ec ? ec.message() : "path already exists");
        return {};
    }
    return load_dir / artifact_path.filename();
}

bool CppModuleBackend::stage_sibling_libraries(
    ModuleRecord& record,
    const std::filesystem::path& artifact_path,
    const std::filesystem::path& load_dir
) {
#ifdef _WIN32
    // Windows resolves adjacent dependencies from the original artifact
    // directory through AddDllDirectory while loading the private module copy.
    // Copying every sibling DLL into the shadow directory gives this backend
    // ownership of libraries that may remain loaded by Python extensions or
    // other modules, making deterministic directory cleanup impossible.
    (void)record;
    (void)artifact_path;
    (void)load_dir;
    return true;
#else
    std::error_code ec;
    std::filesystem::directory_iterator it(artifact_path.parent_path(), ec);
    if (ec) {
        record.error_message = "Failed to enumerate native module dependency directory '" +
            artifact_path.parent_path().string() + "': " + ec.message();
        return false;
    }

    for (const auto& entry : it) {
        if (!entry.is_regular_file(ec) || ec) {
            ec.clear();
            continue;
        }
        if (entry.path().filename() == artifact_path.filename() ||
            !is_dynamic_library_file(entry.path())) {
            continue;
        }

        const std::filesystem::path destination = load_dir / entry.path().filename();
        std::filesystem::copy_file(entry.path(), destination, std::filesystem::copy_options::none, ec);
        if (ec) {
            record.error_message = "Failed to stage native module dependency '" +
                entry.path().string() + "': " + ec.message();
            return false;
        }
    }
    return true;
#endif
}

bool CppModuleBackend::remove_shadow_artifacts(
    ModuleRecord& record,
    const std::filesystem::path& path
) {
    if (path.empty()) {
        return true;
    }

    std::error_code ec;
    const std::filesystem::path load_dir = path.parent_path();
    std::filesystem::remove_all(load_dir, ec);
    if (!ec) {
        return true;
    }

    const std::string cleanup_error = "Failed to remove native shadow load directory '" +
        load_dir.string() + "': " + ec.message();
    tc::Log::error("CppModuleBackend: %s", cleanup_error.c_str());
    if (record.error_message.empty()) {
        record.error_message = cleanup_error;
    } else {
        record.error_message += "; " + cleanup_error;
    }
    return false;
}

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
    record.error_message.clear();
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

    // Copy the artifact into this backend's private session directory to avoid
    // loader caching without polluting the project build tree.
    std::string shadow_error;
    const std::filesystem::path load_path = next_shadow_path(
        config->artifact_path,
        environment,
        shadow_error
    );
    if (load_path.empty()) {
        record.error_message = shadow_error;
        return false;
    }
    try {
        std::filesystem::copy_file(
            config->artifact_path, load_path,
            std::filesystem::copy_options::none
        );
    } catch (const std::exception& e) {
        record.error_message = "Failed to copy artifact for loading: ";
        record.error_message += e.what();
        remove_shadow_artifacts(record, load_path);
        return false;
    }
    if (!stage_sibling_libraries(record, config->artifact_path, load_path.parent_path())) {
        remove_shadow_artifacts(record, load_path);
        return false;
    }

    std::string error;
    const std::filesystem::path sdk_bin_dir = environment.sdk_prefix.empty()
        ? std::filesystem::path{}
        : environment.sdk_prefix / "bin";
    void* native_handle = load_shared_library(
        load_path,
        config->artifact_path.parent_path(),
        sdk_bin_dir,
        error);
    if (native_handle == nullptr) {
        record.error_message = "Failed to load shared library: " + error;
        remove_shadow_artifacts(record, load_path);
        return false;
    }

    const auto* descriptor = reinterpret_cast<
        const termin_native_module_descriptor_v1_data*>(
            resolve_symbol(native_handle, TERMIN_NATIVE_MODULE_DESCRIPTOR_SYMBOL));
    const NativeModuleValidationResult descriptor_validation =
        validate_native_module_descriptor_v1(descriptor, record.spec.id);
    if (!descriptor_validation.compatible) {
        record.error_message = descriptor_validation.error;
        unload_shared_library(native_handle);
        remove_shadow_artifacts(record, load_path);
        return false;
    }

    auto handle = std::make_shared<CppModuleHandle>();
    handle->artifact_path = config->artifact_path;
    handle->loaded_path = load_path;
    handle->native_handle = native_handle;
    handle->module_id = record.spec.id;
    handle->host_api = make_native_module_host_v1(
        handle->module_id.c_str(),
        handle.get()
    );
    handle->host_api.log = native_module_host_log;
    handle->descriptor = descriptor;

    bool init_scope_started = false;
    auto end_init_scope = [&]() {
        if (init_scope_started && environment.after_cpp_module_init) {
            environment.after_cpp_module_init(record);
        }
        init_scope_started = false;
    };
    char error_buffer[2048] = {};
    termin_native_module_error init_error{
        sizeof(termin_native_module_error),
        error_buffer,
        sizeof(error_buffer)
    };
    int32_t init_status = -1;
    try {
        if (environment.before_cpp_module_init) {
            init_scope_started = true;
            environment.before_cpp_module_init(record);
        }
        init_status = descriptor->init(&handle->host_api, &init_error);
        end_init_scope();
    } catch (const std::exception& e) {
        end_init_scope();
        record.error_message = std::string("native module init crossed C ABI with exception: ") + e.what();
    } catch (...) {
        end_init_scope();
        record.error_message = "native module init crossed C ABI with unknown exception";
    }
    if (init_status != 0 || !record.error_message.empty()) {
        if (record.error_message.empty()) {
            record.error_message = native_module_error_message(
                init_status,
                "native module init",
                error_buffer
            );
        }
        char shutdown_buffer[2048] = {};
        termin_native_module_error shutdown_error{
            sizeof(termin_native_module_error),
            shutdown_buffer,
            sizeof(shutdown_buffer)
        };
        try {
            const int32_t shutdown_status = descriptor->shutdown(
                &handle->host_api,
                &shutdown_error
            );
            if (shutdown_status != 0) {
                record.diagnostics += "\n" + native_module_error_message(
                    shutdown_status,
                    "cleanup after failed native module init",
                    shutdown_buffer
                );
            }
        } catch (...) {
            record.diagnostics += "\ncleanup after failed native module init threw across C ABI";
        }
        if (environment.on_cpp_module_load_failure) {
            environment.on_cpp_module_load_failure(record, record.error_message);
        }
        unload_shared_library(native_handle);
        handle->native_handle = nullptr;
        handle->descriptor = nullptr;
        remove_shadow_artifacts(record, load_path);
        return false;
    }

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

    if (!handle->descriptor || !handle->descriptor->shutdown) {
        record.error_message = "native module handle lost its ABI descriptor before shutdown";
        return false;
    }
    char error_buffer[2048] = {};
    termin_native_module_error shutdown_error{
        sizeof(termin_native_module_error),
        error_buffer,
        sizeof(error_buffer)
    };
    int32_t status = -1;
    try {
        status = handle->descriptor->shutdown(&handle->host_api, &shutdown_error);
    } catch (const std::exception& e) {
        record.error_message = std::string("native module shutdown crossed C ABI with exception: ") + e.what();
        return false;
    } catch (...) {
        record.error_message = "native module shutdown crossed C ABI with unknown exception";
        return false;
    }
    if (status != 0) {
        record.error_message = native_module_error_message(
            status,
            "native module shutdown",
            error_buffer
        );
        return false;
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
    handle->descriptor = nullptr;
    return remove_shadow_artifacts(record, handle->loaded_path);
}

ModuleCleanResult CppModuleBackend::clean(
    ModuleRecord& record,
    const ModuleEnvironment& environment
) {
    const auto config = std::dynamic_pointer_cast<CppModuleConfig>(record.spec.config);
    if (!config) {
        record.error_message = "Invalid C++ module config";
        return ModuleCleanResult::Failed;
    }

    if (config->clean_command.empty()) {
        return ModuleCleanResult::NotSupported;
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
        return ModuleCleanResult::Failed;
    }
    record.diagnostics = output;
    return ModuleCleanResult::Succeeded;
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
