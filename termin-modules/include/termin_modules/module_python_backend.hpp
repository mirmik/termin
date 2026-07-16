#pragma once

#include <filesystem>
#include <vector>

#include "termin_modules/module_backend.hpp"
#include "termin_modules/termin_modules_python_api.hpp"

namespace termin_modules {

class TERMIN_MODULES_PYTHON_API PythonModuleBackend : public IModuleBackend {
public:
    ModuleKind kind() const override { return ModuleKind::Python; }

    bool prepare_environment(
        const std::vector<ModuleRecord>& records,
        const ModuleEnvironment& environment,
        std::string& diagnostics,
        std::string& error
    ) override;

    bool teardown_environment(
        const ModuleEnvironment& environment,
        std::string& error
    ) override;

    bool load(
        ModuleRecord& record,
        const ModuleEnvironment& environment
    ) override;

    bool unload(
        ModuleRecord& record,
        const ModuleEnvironment& environment
    ) override;

private:
    bool _environment_prepared = false;
    std::vector<std::filesystem::path> _session_added_paths;

    bool ensure_interpreter(std::string& error) const;
    std::string fetch_python_error() const;
};

} // namespace termin_modules
