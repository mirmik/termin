#pragma once

#include <functional>

#include "termin_modules/module_types.hpp"
#include "termin_modules/termin_modules_api.hpp"

namespace termin_modules {

using BuildOutputCallback = std::function<void(const std::string& module_id, const std::string& line)>;

enum class ModuleCleanResult {
    NotSupported,
    Succeeded,
    Failed,
};

class TERMIN_MODULES_API IModuleBackend {
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

    virtual bool supports_staged_unload() const {
        return false;
    }

    virtual bool begin_unload(
        ModuleRecord& record,
        const ModuleEnvironment& environment
    ) {
        return unload(record, environment);
    }

    virtual bool finish_unload(
        ModuleRecord& record,
        const ModuleEnvironment& environment
    ) {
        (void)record;
        (void)environment;
        return true;
    }

    virtual bool build(
        ModuleRecord& record,
        const ModuleEnvironment& environment
    ) {
        (void)record;
        (void)environment;
        return true;
    }

    virtual ModuleCleanResult clean(
        ModuleRecord& record,
        const ModuleEnvironment& environment
    ) {
        (void)record;
        (void)environment;
        return ModuleCleanResult::NotSupported;
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
