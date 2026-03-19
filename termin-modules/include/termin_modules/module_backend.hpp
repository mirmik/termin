#pragma once

#include "termin_modules/module_types.hpp"

namespace termin_modules {

class IModuleBackend {
public:
    virtual ~IModuleBackend() = default;

    virtual ModuleKind kind() const = 0;

    virtual bool load(
        ModuleRecord& record,
        const ModuleEnvironment& environment
    ) = 0;

    virtual bool unload(
        ModuleRecord& record,
        const ModuleEnvironment& environment
    ) = 0;

    virtual bool clean(
        ModuleRecord& record,
        const ModuleEnvironment& environment
    ) {
        (void)record;
        (void)environment;
        return true;
    }
};

} // namespace termin_modules
