#pragma once

#include "termin_modules/module_backend.hpp"

namespace termin_modules {

class CppModuleBackend : public IModuleBackend {
public:
    ModuleKind kind() const override { return ModuleKind::Cpp; }

    bool load(
        ModuleRecord& record,
        const ModuleEnvironment& environment
    ) override;

    bool unload(
        ModuleRecord& record,
        const ModuleEnvironment& environment
    ) override;

    bool clean(
        ModuleRecord& record,
        const ModuleEnvironment& environment
    ) override;

private:
    bool run_build_command(
        const std::string& command,
        const std::filesystem::path& working_dir,
        const ModuleEnvironment& environment,
        std::string& output,
        std::string& error
    ) const;
};

} // namespace termin_modules
