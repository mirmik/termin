#pragma once

#include <vector>
#include <string>
#include <memory>
#include <nanobind/nanobind.h>

#include "termin/render/geometry_pass_base.hpp"
#include "termin/render/resource_spec.hpp"
#include "termin/render/drawable.hpp"
#include "termin/render/render_context.hpp"
#include "termin/render/graphics_backend.hpp"
#include "termin/render/render_state.hpp"
#include "termin/render/shader_program.hpp"
#include "termin/camera/camera.hpp"
#include "termin/geom/mat44.hpp"
#include "termin/entity/entity.hpp"
#include "termin/entity/component.hpp"
#include "tc_inspect.hpp"
#include "tc_scene.h"

namespace nb = nanobind;

namespace termin {

/**
 * Normal pass - renders world-space normals to texture.
 *
 * Uses a simple normal shader that outputs normals encoded as RGB.
 * Supports skinned meshes via draw_geometry().
 *
 * Output: RGB texture with normals encoded as (normal * 0.5 + 0.5)
 */
class NormalPass : public GeometryPassBase {
public:
    // Pass configuration
    std::string input_res = "empty_normal";
    std::string output_res = "normal";

    // INSPECT_FIELD registrations
    INSPECT_FIELD(NormalPass, input_res, "Input Resource", "string")
    INSPECT_FIELD(NormalPass, output_res, "Output Resource", "string")

    NormalPass(
        const std::string& input_res = "empty_normal",
        const std::string& output_res = "normal",
        const std::string& pass_name = "Normal"
    );

    virtual ~NormalPass() = default;

    // Clean up cached shader
    void destroy() override;

    /**
     * Execute the normal pass.
     */
    void execute_with_data(
        GraphicsBackend* graphics,
        const FBOMap& reads_fbos,
        const FBOMap& writes_fbos,
        const Rect4i& rect,
        tc_scene* scene,
        const Mat44f& view,
        const Mat44f& projection,
        int64_t context_key,
        uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL
    );

    // Legacy execute (required by base class) - does nothing
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

    /**
     * Get internal symbols for debugging.
     */
    // Collect drawable components from entities
    struct NormalDrawCall {
        Entity entity;
        tc_component* component;
    };

    std::vector<NormalDrawCall> collect_draw_calls(tc_scene* scene, uint64_t layer_mask);

private:
    // Normal shader (lazily compiled)
    std::unique_ptr<ShaderProgram> _normal_shader;

    // Get or compile normal shader
    ShaderProgram* get_normal_shader(GraphicsBackend* graphics);
};

} // namespace termin
