#pragma once

#include <cstdint>
#include <filesystem>
#include <functional>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <vector>

#include "termin_modules/native_module_abi.h"
#include "termin_modules/termin_modules_api.hpp"

namespace termin_modules {

    enum class ModuleKind {
        Cpp,
        Python,
    };

    enum class ModuleState {
        Discovered,
        Loading,
        Loaded,
        Unloading,
        CleanupFailed,
        Failed,
        Unloaded,
        Ignored,
    };

    enum class ModuleCleanupPhase {
        None,
        Prepare,
        BackendBegin,
        RevokeContributions,
        BackendFinish,
        BackendUnload,
    };

    struct IModuleConfig {
        virtual ~IModuleConfig() = default;
    };

    struct CppModuleConfig : IModuleConfig {
        std::string build_command;
        std::string clean_command;
        std::filesystem::path artifact_path;
        std::vector<std::filesystem::path> rebuild_inputs;
        bool ignored = false;
    };

    struct PythonModuleConfig : IModuleConfig {
        std::filesystem::path root;
        std::vector<std::string> packages;
        std::vector<std::string> requirements;
        bool ignored = false;
    };

    struct ModuleSpec {
        std::string id;
        ModuleKind kind = ModuleKind::Cpp;
        std::filesystem::path descriptor_path;
        std::vector<std::string> dependencies;
        std::shared_ptr<IModuleConfig> config;
    };

    struct IModuleHandle {
        virtual ~IModuleHandle() = default;
    };

    struct CppModuleHandle : IModuleHandle {
        std::filesystem::path artifact_path;
        std::filesystem::path loaded_path;
        void* native_handle = nullptr;
        std::string module_id;
        termin_native_module_host_v1 host_api{};
        const termin_native_module_descriptor_v1_data* descriptor = nullptr;
        bool shutdown_called = false;
        bool symbols_available = false;
        mutable std::mutex symbols_mutex;
        size_t active_symbol_calls = 0;
    };

    // Pins a call, not a binding. Backend refuses unload while any call is active,
    // including reentrant unload and free-threaded Python callers.
    class TERMIN_MODULES_API NativeModuleCall {
    public:
        NativeModuleCall(std::shared_ptr<CppModuleHandle> handle, uintptr_t address);
        ~NativeModuleCall();
        NativeModuleCall(const NativeModuleCall&) = delete;
        NativeModuleCall& operator=(const NativeModuleCall&) = delete;
        uintptr_t address() const { return _address; }
        void release();
    private:
        std::shared_ptr<CppModuleHandle> _handle;
        uintptr_t _address;
    };

    // Non-owning view of one loaded generation. Never opens or retains an OS
    // library handle. acquire() protects only the duration of a native call.
    class TERMIN_MODULES_API NativeModuleSymbols {
    public:
        explicit NativeModuleSymbols(const std::shared_ptr<CppModuleHandle>& handle);
        bool valid() const;
        uintptr_t resolve(const std::string& name) const;
        std::shared_ptr<NativeModuleCall> acquire(const std::string& name) const;

    private:
        std::weak_ptr<CppModuleHandle> _handle;
        std::string _module_id;
    };

    struct PythonModuleHandle : IModuleHandle {};

    struct ModuleRecord {
        ModuleSpec spec;
        ModuleState state = ModuleState::Discovered;
        ModuleCleanupPhase cleanup_phase = ModuleCleanupPhase::None;
        std::string error_message;
        std::string diagnostics;
        std::shared_ptr<IModuleHandle> handle;
        // Watcher observations also cover deletions and timestamp-preserving
        // edits, which cannot be recovered by scanning existing inputs.
        std::optional<std::filesystem::file_time_type> inputs_changed_at;
        uint64_t input_revision = 0;
    };

    struct ModuleEnvironment {
        std::filesystem::path sdk_prefix;
        std::filesystem::path cmake_prefix_path;
        std::filesystem::path lib_dir;
        std::filesystem::path project_root;
        std::filesystem::path project_venv_path;
        std::filesystem::path native_shadow_root;
        std::string python_executable;
        bool use_project_venv = false;
        bool allow_python_package_install = false;
        bool sync_live_scenes = true;
        std::function<void(const ModuleRecord&)> before_cpp_module_init;
        std::function<void(const ModuleRecord&)> after_cpp_module_init;
        std::function<bool(const ModuleRecord&, const std::string&, std::string&)> on_cpp_module_load_failure;
    };

    enum class ModuleEventKind {
        Discovered,
        Loading,
        Loaded,
        Unloading,
        Unloaded,
        Reloading,
        CleanupFailed,
        Failed,
    };

    struct ModuleEvent {
        ModuleEventKind kind = ModuleEventKind::Discovered;
        std::string module_id;
        std::string message;
    };

} // namespace termin_modules
