#pragma once

#include <vector>
#include <string>
#include <unordered_map>
#include <nanobind/nanobind.h>

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

namespace nb = nanobind;

namespace termin {

// Draw call for shadow pass (defined before ShadowPass class)
struct ShadowDrawCall {
    const Entity* entity = nullptr;
    tc_component* component = nullptr;
    std::string geometry_id;
};

// Result of shadow map rendering for one light
struct ShadowMapResult {
    FramebufferHandle* fbo = nullptr;
    Mat44f light_space_matrix;
    int light_index = 0;

    ShadowMapResult() = default;
    ShadowMapResult(FramebufferHandle* f, const Mat44f& m, int idx)
        : fbo(f), light_space_matrix(m), light_index(idx) {}
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
    int default_resolution = 1024;
    float max_shadow_distance = 50.0f;
    float ortho_size = 20.0f;  // Fallback
    float near = 0.1f;         // Fallback
    float far = 100.0f;        // Fallback
    float caster_offset = 50.0f;

    // Entity names cache (for get_internal_symbols)
    std::vector<std::string> entity_names;

    ShadowPass(
        const std::string& output_res = "shadow_maps",
        const std::string& pass_name = "Shadow",
        int default_resolution = 1024,
        float max_shadow_distance = 50.0f,
        float ortho_size = 20.0f,
        float near = 0.1f,
        float far = 100.0f,
        float caster_offset = 50.0f
    );

    virtual ~ShadowPass() = default;

    /**
     * Execute shadow pass, rendering shadow maps for all lights.
     *
     * @param graphics Graphics backend
     * @param entities Scene entities
     * @param lights Light sources
     * @param camera_view Camera view matrix (for frustum fitting)
     * @param camera_projection Camera projection matrix
     * @param context_key VAO/shader cache key
     * @return Vector of shadow map results
     */
    std::vector<ShadowMapResult> execute_shadow_pass(
        GraphicsBackend* graphics,
        const std::vector<Entity>& entities,
        const std::vector<Light>& lights,
        const Mat44f& camera_view,
        const Mat44f& camera_projection,
        int64_t context_key
    );

    // Legacy execute (required by base class) - not used
    void execute(
        GraphicsBackend* graphics,
        const FBOMap& reads_fbos,
        const FBOMap& writes_fbos,
        const Rect4i& rect,
        void* scene,
        void* camera,
        int64_t context_key,
        const std::vector<Light*>* lights = nullptr
    ) override;

    std::vector<ResourceSpec> get_resource_specs() const override;

    std::vector<std::string> get_internal_symbols() const override {
        return entity_names;
    }

private:
    // FBO pool: index -> FBO
    std::unordered_map<int, FramebufferHandlePtr> fbo_pool_;

    // Shadow shader (created lazily)
    ShaderHandlePtr shadow_shader_;

    // Ensure shadow shader is ready
    void ensure_shader(GraphicsBackend* graphics);

    // Get or create FBO for shadow map
    FramebufferHandle* get_or_create_fbo(GraphicsBackend* graphics, int resolution, int index);

    // Collect shadow caster draw calls
    std::vector<ShadowDrawCall> collect_shadow_casters(const std::vector<Entity>& entities);

    // Build shadow camera params for a light
    ShadowCameraParams build_shadow_params(
        const Light& light,
        const Mat44f& camera_view,
        const Mat44f& camera_projection
    );
};

} // namespace termin
