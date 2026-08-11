#pragma once

#include <set>
#include <string>
#include <vector>

#include <termin/render/frame_pass.hpp>
#include <termin/render/material_pipeline_shader_assembler.hpp>
#include <termin/render/resource_spec.hpp>
#include <termin/render/scene_shader_usage_provider.hpp>
#include <termin/render_passes/export.h>

namespace termin {

    struct StandardGBufferPassConfig {
        std::string base_ao_res = "gbuffer_base_ao";
        std::string normal_rough_res = "gbuffer_normal_rough";
        std::string metal_emit_res = "gbuffer_metal_emit";
        std::string depth_res = "scene_depth";
        std::string camera_name;
        std::string pass_name = "StandardGBuffer";
    };

    TERMIN_RENDER_PASSES_API MaterialPipelinePassContract standard_gbuffer_material_pass_contract();

    class TERMIN_RENDER_PASSES_API StandardGBufferPass final : public CxxFramePass, public SceneShaderUsageProvider {
    public:
        std::string base_ao_res = "gbuffer_base_ao";
        std::string normal_rough_res = "gbuffer_normal_rough";
        std::string metal_emit_res = "gbuffer_metal_emit";
        std::string depth_res = "scene_depth";
        std::string camera_name;

        INSPECT_FIELD(StandardGBufferPass, base_ao_res, "Base + AO", "string")
        INSPECT_FIELD(StandardGBufferPass, normal_rough_res, "Normal + Roughness", "string")
        INSPECT_FIELD(StandardGBufferPass, metal_emit_res, "Metallic + Emission", "string")
        INSPECT_FIELD(StandardGBufferPass, depth_res, "Scene Depth", "string")
        INSPECT_FIELD(StandardGBufferPass, camera_name, "Camera", "string")
        INSPECT_TYPE_METADATA(StandardGBufferPass,
                              graph,
                              make_pass_graph_metadata({},
                                                       {{"base_ao_res", "color_texture"},
                                                        {"normal_rough_res", "color_texture"},
                                                        {"metal_emit_res", "color_texture"},
                                                        {"depth_res", "depth_texture"}}))

        explicit StandardGBufferPass(const StandardGBufferPassConfig& config = {});

        static void register_type();

        void execute(ExecuteContext& ctx) override;
        void collect_scene_shader_usages(tc_scene_handle scene,
                                         const std::function<void(TcShader)>& emit) const override;

        std::set<const char*> compute_reads() const override;
        std::set<const char*> compute_writes() const override;
        std::vector<ResourceSpec> get_resource_specs() const override;
    };

} // namespace termin
