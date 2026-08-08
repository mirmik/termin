#pragma once

#include <termin/render/frame_pass.hpp>
#include <termin/render_passes/export.h>

#include <tgfx/frame_graph_resource.hpp>
#include <tgfx2/handles.hpp>

#include <array>
#include <cstdint>
#include <string>

namespace tgfx {
    class IRenderDevice;
}

namespace termin {

    // Portable split-sum IBL data. Environment directions are encoded into
    // ordinary 2D octahedral textures so every tgfx2 backend can consume the
    // same resource without requiring cubemap or texture-array support.
    class TERMIN_RENDER_PASSES_API EnvironmentLightingResource : public FrameGraphResource {
    public:
        tgfx::TextureHandle diffuse_irradiance;
        tgfx::TextureHandle prefiltered_specular;
        tgfx::TextureHandle brdf_lut;
        tgfx::SamplerHandle sampler;
        uint32_t specular_mip_count = 0;

        const char* resource_type() const override {
            return "environment_lighting";
        }

        bool ready() const {
            return diffuse_irradiance && prefiltered_specular && brdf_lut && sampler && specular_mip_count > 0;
        }

        void clear() {
            diffuse_irradiance = {};
            prefiltered_specular = {};
            brdf_lut = {};
            sampler = {};
            specular_mip_count = 0;
        }
    };

    TERMIN_RENDER_PASSES_API bool register_environment_lighting_resource_type();

    class TERMIN_RENDER_PASSES_API EnvironmentLightingPass : public CxxFramePass {
    public:
        std::string output_res = "environment_lighting";

    private:
        tgfx::IRenderDevice* device_ = nullptr;
        tgfx::TextureHandle diffuse_irradiance_;
        tgfx::TextureHandle prefiltered_specular_;
        tgfx::TextureHandle brdf_lut_;
        tgfx::SamplerHandle sampler_;
        std::array<float, 11> cached_signature_{};
        bool has_cached_signature_ = false;

    public:
        static void register_type();

        INSPECT_FIELD(EnvironmentLightingPass, output_res, "Output", "string")
        INSPECT_TYPE_METADATA(EnvironmentLightingPass,
                              graph,
                              make_pass_graph_metadata({}, {{"output_res", "environment_lighting"}}))

        explicit EnvironmentLightingPass(const std::string& output = "environment_lighting",
                                         const std::string& pass_name = "EnvironmentLighting");

        std::set<const char*> compute_reads() const override;
        std::set<const char*> compute_writes() const override;
        std::vector<ResourceSpec> get_resource_specs() const override;
        void execute(ExecuteContext& ctx) override;
        void destroy() override;

    private:
        void destroy_gpu_resources();
    };

} // namespace termin
