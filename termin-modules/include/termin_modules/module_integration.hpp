#pragma once

#include <functional>
#include <memory>
#include <string>

#include "termin_modules/module_types.hpp"

namespace termin_modules {

struct IModuleReloadState {
    virtual ~IModuleReloadState() = default;
};

struct CppModuleCallbacks {
    std::function<void(const ModuleRecord&)> before_load;
    std::function<void(const ModuleRecord&)> after_load;
    std::function<void(const ModuleRecord&)> before_unload;
    std::function<void(const ModuleRecord&)> after_unload;
    std::function<void(const ModuleRecord&)> after_reload;
    std::function<void(const ModuleRecord&, const std::string&)> after_failed_load;
    std::function<std::shared_ptr<IModuleReloadState>(const ModuleRecord&)> capture_reload_state;
    std::function<bool(const ModuleRecord&, const std::shared_ptr<IModuleReloadState>&, std::string&)> restore_reload_state;
};

struct PythonModuleCallbacks {
    std::function<void(const ModuleRecord&)> before_load;
    std::function<void(const ModuleRecord&)> after_load;
    std::function<void(const ModuleRecord&)> before_unload;
    std::function<void(const ModuleRecord&)> after_unload;
    std::function<void(const ModuleRecord&)> after_reload;
    std::function<void(const ModuleRecord&, const std::string&)> after_failed_load;
    std::function<std::shared_ptr<IModuleReloadState>(const ModuleRecord&)> capture_reload_state;
    std::function<bool(const ModuleRecord&, const std::shared_ptr<IModuleReloadState>&, std::string&)> restore_reload_state;
};

} // namespace termin_modules
