#pragma once

#include <vector>
#include <string>
#include <unordered_map>

#ifdef TERMIN_HAS_NANOBIND
#include <nanobind/nanobind.h>
namespace nb = nanobind;
#endif

#include "termin/render/render_frame_pass.hpp"
#include "termin/render/resource_spec.hpp"
#include "termin/render/drawable.hpp"
#include "termin/render/render_context.hpp"
#include "termin/render/graphics_backend.hpp"
#include "termin/render/render_state.hpp"
#include "termin/render/handles.hpp"
#include "termin/lighting/light.hpp"
#include "termin/render/shadow_camera.hpp"
#include "termin/geom/mat44.hpp"
#include "termin/entity/entity.hpp"
#include "tc_scene.h"
#ifdef TERMIN_HAS_NANOBIND
#include "tc_inspect.hpp"
#else
#include "tc_inspect_cpp.hpp"
#endif
#include "tc_shader_handle.hpp"

namespace termin {

// Draw call for shadow pass (defined before ShadowPass class)
struct ShadowDrawCall {
    Entity entity;
    tc_component* component = nullptr;
    int geometry_id = 0;
};

// Result of shadow map rendering for one light (or cascade)
struct ShadowMapResult {
    FramebufferHandle* fbo = nullptr;
    Mat44f light_space_matrix;
    int light_index = 0;

    // Cascade parameters
    int cascade_index = 0;
    float cascade_split_near = 0.0f;
    float cascade_split_far = 0.0f;

    ShadowMapResult() = default;
    ShadowMapResult(FramebufferHandle* f, const Mat44f& m, int idx)
        : fbo(f), light_space_matrix(m), light_index(idx) {}

    ShadowMapResult(FramebufferHandle* f, const Mat44f& m, int light_idx,
                    int cascade_idx, float split_near, float split_far)
        : fbo(f), light_space_matrix(m), light_index(light_idx),
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
class ShadowPass : public RenderFramePass {
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

    // Non-copyable (contains unique_ptr in fbo_pool_)
    ShadowPass(const ShadowPass&) = delete;
    ShadowPass& operator=(const ShadowPass&) = delete;
    ShadowPass(ShadowPass&&) = default;
    ShadowPass& operator=(ShadowPass&&) = default;

    // Clean up FBO pool
    void destroy() override;

    /**
     * Execute shadow pass, rendering shadow maps for all lights.
     *
     * @param graphics Graphics backend
     * @param scene Scene pointer (tc_scene)
     * @param lights Light sources
     * @param camera_view Camera view matrix (for frustum fitting)
     * @param camera_projection Camera projection matrix
     * @return Vector of shadow map results
     */
    std::vector<ShadowMapResult> execute_shadow_pass(
        GraphicsBackend* graphics,
        tc_scene* scene,
        const std::vector<Light>& lights,
        const Mat44f& camera_view,
        const Mat44f& camera_projection
    );

    // Legacy execute (required by base class) - not used
    void execute(
        GraphicsBackend* graphics,
        const FBOMap& reads_fbos,
        const FBOMap& writes_fbos,
        const Rect4i& rect,
        void* scene,
        void* camera,
        const std::vector<Light*>* lights = nullptr
    ) override;

    std::vector<ResourceSpec> get_resource_specs() const override;

    std::vector<std::string> get_internal_symbols() const override {
        return entity_names;
    }

    // Shadow shader - set from Python before execute
    TcShader* shadow_shader = nullptr;

private:
    // FBO pool: index -> FBO
    std::unordered_map<int, FramebufferHandlePtr> fbo_pool_;

    // Get or create FBO for shadow map
    FramebufferHandle* get_or_create_fbo(GraphicsBackend* graphics, int resolution, int index);

    // Collect shadow caster draw calls
    std::vector<ShadowDrawCall> collect_shadow_casters(tc_scene* scene);

    // Build shadow camera params for a light
    ShadowCameraParams build_shadow_params(
        const Light& light,
        const Mat44f& camera_view,
        const Mat44f& camera_projection
    );
};

} // namespace termin
