#pragma once

#include <filesystem>
#include <functional>
#include <memory>
#include <string>
#include <vector>

#include "termin_modules/native_module_abi.h"

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
};

struct PythonModuleHandle : IModuleHandle {};

struct ModuleRecord {
    ModuleSpec spec;
    ModuleState state = ModuleState::Discovered;
    ModuleCleanupPhase cleanup_phase = ModuleCleanupPhase::None;
    std::string error_message;
    std::string diagnostics;
    std::shared_ptr<IModuleHandle> handle;
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
    std::function<void(const ModuleRecord&, const std::string&)>
        on_cpp_module_load_failure;
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
