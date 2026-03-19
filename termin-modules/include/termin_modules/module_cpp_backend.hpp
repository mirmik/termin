#pragma once

#include "termin_modules/module_backend.hpp"

namespace termin_modules {

class CppModuleBackend : public IModuleBackend {
public:
    BuildOutputCallback _output_callback;

    ModuleKind kind() const override { return ModuleKind::Cpp; }

    bool load(
        ModuleRecord& record,
        const ModuleEnvironment& environment
    ) override;

    bool build(
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

    bool needs_rebuild(
        const ModuleRecord& record,
        const ModuleEnvironment& environment
    ) override;

    void set_output_callback(BuildOutputCallback callback) override;

private:
    bool run_build_command(
        const std::string& module_id,
        const std::string& command,
        const std::filesystem::path& working_dir,
        const ModuleEnvironment& environment,
        std::string& output,
        std::string& error
    ) const;
};

} // namespace termin_modules
