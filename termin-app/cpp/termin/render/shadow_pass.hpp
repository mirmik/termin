#pragma once

#include <vector>
#include <string>
#include <unordered_map>

#include "termin/render/frame_pass.hpp"
#include "termin/render/execute_context.hpp"
#include "termin/render/resource_spec.hpp"
#include "termin/lighting/shadow.hpp"
#include "termin/render/drawable.hpp"
#include "termin/render/render_context.hpp"
#include "tgfx/render_state.hpp"
#include "tgfx/handles.hpp"
#include "tgfx2/handles.hpp"
#include "tgfx2/i_render_device.hpp"
#include <termin/render/light.hpp>
#include "termin/render/shadow_camera.hpp"
#include <termin/geom/mat44.hpp>
#include <termin/entity/entity.hpp>
#include "core/tc_scene.h"
#include "core/tc_scene_pool.h"
#include "tc_inspect_cpp.hpp"
#include <tgfx/tgfx_shader_handle.hpp>
extern "C" {
#include <tgfx/resources/tc_shader_registry.h>
}

namespace termin {

// Draw call for shadow pass (defined before ShadowPass class)
struct ShadowDrawCall {
    Entity entity;
    tc_component* component = nullptr;
    tc_shader_handle final_shader;  // Shader after override (skinning, alpha-test, etc.)
    int geometry_id = 0;
};

// Result of shadow map rendering for one light (or cascade)
struct ShadowMapResult {
    tgfx::TextureHandle depth_tex2;
    int width = 0;
    int height = 0;
    Mat44f light_space_matrix;
    int light_index = 0;

    // Cascade parameters
    int cascade_index = 0;
    float cascade_split_near = 0.0f;
    float cascade_split_far = 0.0f;

    ShadowMapResult() = default;

    ShadowMapResult(tgfx::TextureHandle d, int w, int h,
                    const Mat44f& m, int light_idx,
                    int cascade_idx, float split_near, float split_far)
        : depth_tex2(d), width(w), height(h),
          light_space_matrix(m), light_index(light_idx),
          cascade_index(cascade_idx), cascade_split_near(split_near),
          cascade_split_far(split_far) {}
};

/**
 * Shadow pass - renders shadow maps for directional lights.
 *
 * For each light with shadows enabled:
 * 1. Creates/gets shadow FBO from pool
 * 2. Computes light-space matrix (frustum fitting)
 * 3. Renders shadow casters to depth buffer
 *
 * Returns list of ShadowMapResult for use by ColorPass.
 */
class ShadowPass : public CxxFramePass {
public:
    // Pass configuration
    std::string output_res = "shadow_maps";
    float caster_offset = 50.0f;

    // Entity names cache (for get_internal_symbols)
    std::vector<std::string> entity_names;

    // INSPECT_FIELD registrations
    INSPECT_FIELD(ShadowPass, output_res, "Output Resource", "string")
    INSPECT_FIELD(ShadowPass, caster_offset, "Caster Offset", "float", 0.0, 200.0, 5.0)

    ShadowPass(
        const std::string& output_res = "shadow_maps",
        const std::string& pass_name = "Shadow",
        float caster_offset = 50.0f
    );

    virtual ~ShadowPass() = default;

    // Dynamic resource computation
    std::set<const char*> compute_reads() const override {
        return {};
    }

    std::set<const char*> compute_writes() const override {
        return {output_res.c_str()};
    }

    // Non-copyable (owns tgfx2 texture handles in depth_pool_)
    ShadowPass(const ShadowPass&) = delete;
    ShadowPass& operator=(const ShadowPass&) = delete;
    ShadowPass(ShadowPass&&) = default;
    ShadowPass& operator=(ShadowPass&&) = default;

    // Clean up FBO pool
    void destroy() override;

    // Override from CxxFramePass
    void execute(ExecuteContext& ctx) override;

    // Execute shadow pass, rendering shadow maps for all lights
    // through a tgfx2 RenderContext2. Requires ctx.ctx2 to be non-null.
    std::vector<ShadowMapResult> execute_shadow_pass_tgfx2(
        ExecuteContext& ctx,
        tc_scene_handle scene,
        const std::vector<Light>& lights,
        const Mat44f& camera_view,
        const Mat44f& camera_projection,
        uint64_t layer_mask = 0
    );

    std::vector<ResourceSpec> get_resource_specs() const override;

    std::vector<std::string> get_internal_symbols() const override {
        return entity_names;
    }

private:
    // Lazy tgfx2 state owned by the pass.
    //
    // PerFrame data is written into the device ring UBO per cascade now;
    // the dynamic descriptor offset bakes a fresh offset into each draw,
    // which is what the old per_frame_ubo_pool_ achieved with one VkBuffer
    // per cascade slot (Vulkan cmd-buffer deferred read + shared UBO =
    // stale data bug, vulkan_ubo_reuse_pitfall). Shader handles are NOT
    // owned — they live on the tc_shader global registry so repeated pass
    // construction/destruction doesn't re-run shaderc.
    tgfx::IRenderDevice* device2_ = nullptr;
    tc_shader_handle shadow_shader_handle_ = tc_shader_handle_invalid();

    void ensure_tgfx2_resources(tgfx::IRenderDevice& device);
    void release_tgfx2_resources();

    // Native shadow-map pool: index -> depth texture.
    // Owned via tgfx2 IRenderDevice. Destroyed in destroy().
    struct ShadowDepthSlot {
        tgfx::TextureHandle tex;
        int resolution = 0;
    };
    std::unordered_map<int, ShadowDepthSlot> depth_pool_;
    tgfx::IRenderDevice* depth_pool_device_ = nullptr;

    // Cached draw calls (reused between frames)
    std::vector<ShadowDrawCall> cached_draw_calls_;

    // Get or create native depth texture for shadow map at (index, resolution).
    tgfx::TextureHandle get_or_create_depth_tex2(
        tgfx::IRenderDevice& device, int resolution, int index);

    // Collect shadow caster draw calls
    void collect_shadow_casters(tc_scene_handle scene, uint64_t layer_mask);

    // Sort draw calls by shader
    void sort_draw_calls_by_shader();

    // Build shadow camera params for a light
    ShadowCameraParams build_shadow_params(
        const Light& light,
        const Mat44f& camera_view,
        const Mat44f& camera_projection
    );
};

} // namespace termin
