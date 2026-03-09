#pragma once

#include "termin_modules/module_backend.hpp"

namespace termin_modules {

class PythonModuleBackend : public IModuleBackend {
public:
    ModuleKind kind() const override { return ModuleKind::Python; }

    bool load(
        ModuleRecord& record,
        const ModuleEnvironment& environment
    ) override;

    bool unload(
        ModuleRecord& record,
        const ModuleEnvironment& environment
    ) override;

private:
    bool ensure_interpreter(std::string& error) const;
    std::string fetch_python_error() const;
};

} // namespace termin_modules
