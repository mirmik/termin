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
 * ID pass - renders entity pick IDs to texture for picking.
 *
 * Uses a simple pick shader that outputs pick color.
 * Supports skinned meshes via override_shader().
 *
 * Output: RGB texture with entity pick IDs encoded as colors.
 */
class IdPass : public GeometryPassBase {
public:
    // Pass configuration
    std::string input_res = "empty";
    std::string output_res = "id";

    // INSPECT_FIELD registrations
    INSPECT_FIELD(IdPass, input_res, "Input Resource", "string")
    INSPECT_FIELD(IdPass, output_res, "Output Resource", "string")

    IdPass(
        const std::string& input_res = "empty",
        const std::string& output_res = "id",
        const std::string& pass_name = "IdPass"
    );

    virtual ~IdPass() = default;

    // Clean up cached shader
    void destroy() override;

    /**
     * Execute the ID pass.
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
    // Collect drawable components from pickable entities
    struct IdDrawCall {
        Entity entity;
        tc_component* component;
        int pick_id;
    };

    std::vector<IdDrawCall> collect_draw_calls(tc_scene* scene, uint64_t layer_mask);

private:
    // Pick shader (lazily compiled)
    std::unique_ptr<ShaderProgram> _pick_shader;

    // Get or compile pick shader
    ShaderProgram* get_pick_shader(GraphicsBackend* graphics);

    // Convert pick ID to RGB color
    static void id_to_rgb(int id, float& r, float& g, float& b);

    // Call debugger blit if debug point matches entity name
    void maybe_blit_to_debugger(
        GraphicsBackend* graphics,
        FramebufferHandle* fb,
        const std::string& entity_name,
        int width,
        int height
    );
};

} // namespace termin
