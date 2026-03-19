#pragma once

#include <functional>

#include "termin_modules/module_types.hpp"

namespace termin_modules {

using BuildOutputCallback = std::function<void(const std::string& module_id, const std::string& line)>;

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

    virtual bool build(
        ModuleRecord& record,
        const ModuleEnvironment& environment
    ) {
        (void)record;
        (void)environment;
        return true;
    }

    virtual bool clean(
        ModuleRecord& record,
        const ModuleEnvironment& environment
    ) {
        (void)record;
        (void)environment;
        return true;
    }

    virtual bool needs_rebuild(
        const ModuleRecord& record,
        const ModuleEnvironment& environment
    ) {
        (void)record;
        (void)environment;
        return false;
    }

    virtual void set_output_callback(BuildOutputCallback callback) {
        (void)callback;
    }
};

} // namespace termin_modules
