#pragma once

#include <vector>
#include <string>
#include <set>
#include <algorithm>

#include "termin/render/render_frame_pass.hpp"
#include "termin/render/resource_spec.hpp"
#include "termin/render/drawable.hpp"
#include "termin/render/render_context.hpp"
#include "termin/render/graphics_backend.hpp"
#include "termin/render/render_state.hpp"
#include "termin/lighting/light.hpp"
#include "termin/lighting/lighting_upload.hpp"
#include "termin/camera/camera.hpp"
#include "termin/geom/mat44.hpp"
#include "termin/entity/entity.hpp"
#include "termin/entity/component.hpp"

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
    std::string phase_mark = "opaque";
    bool sort_by_distance = false;
    bool clear_depth = false;

    ColorPass(
        const std::string& input_res = "empty",
        const std::string& output_res = "color",
        const std::string& phase_mark = "opaque",
        const std::string& pass_name = "Color",
        bool sort_by_distance = false,
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
        const std::vector<Entity*>& entities,
        const Mat44f& view,
        const Mat44f& projection,
        const Vec3& camera_position,
        int64_t context_key,
        const std::vector<Light>& lights,
        const Vec3& ambient_color,
        float ambient_intensity
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

private:
    /**
     * Collect draw calls from entities.
     */
    std::vector<PhaseDrawCall> collect_draw_calls(
        const std::vector<Entity*>& entities,
        const std::string& phase_mark
    );
};

} // namespace termin
