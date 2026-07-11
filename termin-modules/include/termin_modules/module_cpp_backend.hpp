#pragma once

#include <atomic>
#include <cstdint>
#include <mutex>

#include "termin_modules/module_backend.hpp"

namespace termin_modules {

class TERMIN_MODULES_API CppModuleBackend : public IModuleBackend {
private:
    std::filesystem::path _shadow_base_dir;
    std::filesystem::path _shadow_session_dir;
    std::atomic<uint64_t> _shadow_counter{0};
    std::mutex _shadow_mutex;

public:
    BuildOutputCallback _output_callback;

    CppModuleBackend() = default;
    ~CppModuleBackend() noexcept override;

    CppModuleBackend(const CppModuleBackend&) = delete;
    CppModuleBackend& operator=(const CppModuleBackend&) = delete;
    CppModuleBackend(CppModuleBackend&&) = delete;
    CppModuleBackend& operator=(CppModuleBackend&&) = delete;

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

    bool supports_staged_unload() const override { return true; }

    bool begin_unload(
        ModuleRecord& record,
        const ModuleEnvironment& environment
    ) override;

    bool finish_unload(
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


    bool ensure_shadow_session(
        const ModuleEnvironment& environment,
        std::string& error
    );
    std::filesystem::path next_shadow_path(
        const std::filesystem::path& artifact_path,
        const ModuleEnvironment& environment,
        std::string& error
    );
    bool stage_sibling_libraries(
        ModuleRecord& record,
        const std::filesystem::path& artifact_path,
        const std::filesystem::path& load_dir
    );
    bool remove_shadow_artifacts(ModuleRecord& record, const std::filesystem::path& path);
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
