#pragma once

#include <vector>
#include <string>
#include <set>
#include <algorithm>
#include <nanobind/nanobind.h>

#include "termin/render/render_frame_pass.hpp"
#include "termin/render/resource_spec.hpp"
#include "termin/render/drawable.hpp"
#include "termin/render/render_context.hpp"
#include "termin/render/graphics_backend.hpp"
#include "termin/render/render_state.hpp"
#include "termin/lighting/light.hpp"
#include "termin/lighting/shadow.hpp"
#include "termin/lighting/lighting_upload.hpp"
#include "termin/camera/camera.hpp"
#include "termin/geom/mat44.hpp"
#include "termin/entity/entity.hpp"
#include "termin/entity/component.hpp"
#include "tc_inspect.hpp"

namespace nb = nanobind;

namespace termin {

/**
 * Color pass - main rendering pass for opaque/transparent objects.
 *
 * Collects all Drawable components from entities, filters by phase_mark,
 * sorts by priority, and renders with materials and lighting.
 */
class ColorPass : public RenderFramePass {
public:
    // Pass configuration
    std::string input_res = "empty";
    std::string output_res = "color";
    std::string shadow_res = "shadow_maps";  // Shadow map resource name (empty = no shadows)
    std::string phase_mark = "opaque";
    std::string sort_mode = "none";  // "none", "near_to_far", "far_to_near"
    bool clear_depth = false;
    bool wireframe = false;  // Render as wireframe (override polygon mode)

    // Entity names cache (for get_internal_symbols)
    std::vector<std::string> entity_names;

    // INSPECT_FIELD registrations
    INSPECT_FIELD(ColorPass, input_res, "Input Resource", "string")
    INSPECT_FIELD(ColorPass, output_res, "Output Resource", "string")
    INSPECT_FIELD(ColorPass, shadow_res, "Shadow Resource", "string")
    INSPECT_FIELD(ColorPass, phase_mark, "Phase Mark", "string")
    INSPECT_FIELD_CHOICES(ColorPass, sort_mode, "Sort Mode", "string",
        {"none", "None"}, {"near_to_far", "Near to Far"}, {"far_to_near", "Far to Near"})
    INSPECT_FIELD(ColorPass, clear_depth, "Clear Depth", "bool")

    ColorPass(
        const std::string& input_res = "empty",
        const std::string& output_res = "color",
        const std::string& shadow_res = "shadow_maps",
        const std::string& phase_mark = "opaque",
        const std::string& pass_name = "Color",
        const std::string& sort_mode = "none",
        bool clear_depth = false
    );

    virtual ~ColorPass() = default;

    /**
     * Execute the color pass.
     *
     * @param graphics Graphics backend
     * @param reads_fbos Input FBOs
     * @param writes_fbos Output FBOs
     * @param rect Viewport rectangle
     * @param entities List of entities to render
     * @param view View matrix
     * @param projection Projection matrix
     * @param camera_position Camera world position (for distance sorting)
     * @param context_key VAO/shader cache key
     * @param lights Light sources
     * @param ambient_color Ambient light color
     * @param ambient_intensity Ambient light intensity
     */
    void execute_with_data(
        GraphicsBackend* graphics,
        const FBOMap& reads_fbos,
        const FBOMap& writes_fbos,
        const Rect4i& rect,
        const std::vector<Entity>& entities,
        const Mat44f& view,
        const Mat44f& projection,
        const Vec3& camera_position,
        int64_t context_key,
        const std::vector<Light>& lights,
        const Vec3& ambient_color,
        float ambient_intensity,
        const std::vector<ShadowMapEntry>& shadow_maps,
        const ShadowSettings& shadow_settings
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
    std::vector<std::string> get_internal_symbols() const override {
        return entity_names;
    }

private:
    // Collect draw calls from entities.
    std::vector<PhaseDrawCall> collect_draw_calls(
        const std::vector<Entity>& entities,
        const std::string& phase_mark
    );

    /**
     * Call debugger blit if debug point matches entity name.
     */
    void maybe_blit_to_debugger(
        GraphicsBackend* graphics,
        FramebufferHandle* fb,
        const std::string& entity_name,
        int width,
        int height
    );
};

} // namespace termin
