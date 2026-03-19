#pragma once

#include <filesystem>
#include <memory>
#include <string>
#include <vector>

namespace termin_modules {

enum class ModuleKind {
    Cpp,
    Python,
};

enum class ModuleState {
    Discovered,
    Loaded,
    Failed,
    Unloaded,
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
    std::vector<std::string> components;
    std::shared_ptr<IModuleConfig> config;
};

struct IModuleHandle {
    virtual ~IModuleHandle() = default;
};

struct CppModuleHandle : IModuleHandle {
    std::filesystem::path artifact_path;
    std::filesystem::path loaded_path;
    void* native_handle = nullptr;
};

struct PythonModuleHandle : IModuleHandle {
    std::vector<std::string> imported_modules;
    std::vector<std::filesystem::path> added_paths;
};

struct ModuleRecord {
    ModuleSpec spec;
    ModuleState state = ModuleState::Discovered;
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
    std::string python_executable;
    bool use_project_venv = false;
    bool allow_python_package_install = false;
};

enum class ModuleEventKind {
    Discovered,
    Loading,
    Loaded,
    Unloading,
    Unloaded,
    Reloading,
    Failed,
};

struct ModuleEvent {
    ModuleEventKind kind = ModuleEventKind::Discovered;
    std::string module_id;
    std::string message;
};

} // namespace termin_modules
