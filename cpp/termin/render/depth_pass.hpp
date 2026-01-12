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
 * Depth pass - renders linear depth to texture.
 *
 * Uses a simple depth shader that outputs linear depth.
 * Supports skinned meshes via draw_geometry().
 *
 * Output: R16F texture with linear depth normalized to [0, 1]
 * where 0 = near plane, 1 = far plane.
 */
class DepthPass : public GeometryPassBase {
public:
    // Pass configuration
    std::string input_res = "empty_depth";
    std::string output_res = "depth";

    // INSPECT_FIELD registrations
    INSPECT_FIELD(DepthPass, input_res, "Input Resource", "string")
    INSPECT_FIELD(DepthPass, output_res, "Output Resource", "string")

    DepthPass(
        const std::string& input_res = "empty_depth",
        const std::string& output_res = "depth",
        const std::string& pass_name = "Depth"
    );

    virtual ~DepthPass() = default;

    // Clean up cached shader
    void destroy() override;

    /**
     * Execute the depth pass.
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
        float near_plane,
        float far_plane,
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
private:
    // Depth shader (lazily compiled)
    std::unique_ptr<ShaderProgram> _depth_shader;

    // Get or compile depth shader
    ShaderProgram* get_depth_shader(GraphicsBackend* graphics);
};

} // namespace termin
