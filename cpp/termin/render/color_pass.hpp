#pragma once

#include <vector>
#include <string>
#include <set>
#include <algorithm>
#include <unordered_map>

#include "termin/render/frame_pass.hpp"
#include "termin/render/execute_context.hpp"
#include "termin/render/resource_spec.hpp"
#include "termin/render/drawable.hpp"
#include "termin/render/render_context.hpp"
#include "termin/render/graphics_backend.hpp"
#include "termin/render/render_state.hpp"
#include "termin/lighting/light.hpp"
#include "termin/lighting/shadow.hpp"
#include "termin/lighting/lighting_upload.hpp"
#include "termin/lighting/lighting_ubo.hpp"
#include "termin/camera/camera.hpp"
#include "termin/camera/camera_component.hpp"
#include "termin/geom/mat44.hpp"
#include "termin/entity/entity.hpp"
#include "termin/entity/component.hpp"
#ifdef TERMIN_HAS_NANOBIND
#include "tc_inspect.hpp"
#else
#include "tc_inspect_cpp.hpp"
#endif
#include "tc_scene.h"
#include "tc_scene_pool.h"

namespace termin {

/**
 * Color pass - main rendering pass for opaque/transparent objects.
 *
 * Collects all Drawable components from entities, filters by phase_mark,
 * sorts by priority, and renders with materials and lighting.
 */
// Starting texture unit for extra textures (after shadow maps 8-23)
constexpr int EXTRA_TEXTURE_UNIT_START = 24;

class ColorPass : public CxxFramePass {
public:
    // Pass configuration
    std::string input_res = "empty";
    std::string output_res = "color";
    std::string shadow_res = "shadow_maps";  // Shadow map resource name (empty = no shadows)
    std::string phase_mark = "opaque";
    std::string sort_mode = "none";  // "none", "near_to_far", "far_to_near"
    std::string camera_name;  // Override camera by entity name (empty = use context camera)
    bool clear_depth = false;
    bool wireframe = false;  // Render as wireframe (override polygon mode)
    bool use_ubo = false;    // Use UBO for lighting (faster, requires LIGHTING_USE_UBO in shaders)

    // Extra texture resources: uniform_name -> resource_name
    // These are bound before rendering and passed to shaders
    std::unordered_map<std::string, std::string> extra_textures;

    // Entity names cache (for get_internal_symbols)
    std::vector<std::string> entity_names;

    // Last GPU time in milliseconds (from detailed profiling)
    double last_gpu_time_ms() const { return last_gpu_time_ms_; }

    // Extra texture uniforms: uniform_name -> texture_unit (computed during execute)
    std::unordered_map<std::string, int> extra_texture_uniforms;

    // INSPECT_FIELD registrations
    INSPECT_FIELD(ColorPass, input_res, "Input Resource", "string")
    INSPECT_FIELD(ColorPass, output_res, "Output Resource", "string")
    INSPECT_FIELD(ColorPass, shadow_res, "Shadow Resource", "string")
    INSPECT_FIELD(ColorPass, phase_mark, "Phase Mark", "string")
    INSPECT_FIELD_CHOICES(ColorPass, sort_mode, "Sort Mode", "string",
        {"none", "None"}, {"near_to_far", "Near to Far"}, {"far_to_near", "Far to Near"})
    INSPECT_FIELD(ColorPass, clear_depth, "Clear Depth", "bool")
    INSPECT_FIELD(ColorPass, camera_name, "Camera", "string")

    ColorPass(
        const std::string& input_res = "empty",
        const std::string& output_res = "color",
        const std::string& shadow_res = "shadow_maps",
        const std::string& phase_mark = "opaque",
        const std::string& pass_name = "Color",
        const std::string& sort_mode = "none",
        bool clear_depth = false,
        const std::string& camera_name = ""
    );

    virtual ~ColorPass() = default;

    // Clear extra texture uniforms (call after execute)
    void clear_extra_textures() { extra_texture_uniforms.clear(); }

    // Set extra texture uniform
    void set_extra_texture_uniform(const std::string& name, int unit) {
        extra_texture_uniforms[name] = unit;
    }

    /**
     * Execute the color pass.
     *
     * @param graphics Graphics backend
     * @param reads_fbos Input FBOs
     * @param writes_fbos Output FBOs
     * @param rect Viewport rectangle
     * @param scene Scene containing entities to render
     * @param view View matrix
     * @param projection Projection matrix
     * @param camera_position Camera world position (for distance sorting)
     * @param lights Light sources
     * @param ambient_color Ambient light color
     * @param ambient_intensity Ambient light intensity
     * @param layer_mask Layer mask for filtering entities
     */
    void execute_with_data(
        GraphicsBackend* graphics,
        const FBOMap& reads_fbos,
        const FBOMap& writes_fbos,
        const Rect4i& rect,
        tc_scene_handle scene,
        const Mat44f& view,
        const Mat44f& projection,
        const Vec3& camera_position,
        const std::vector<Light>& lights,
        const Vec3& ambient_color,
        float ambient_intensity,
        const std::vector<ShadowMapArrayEntry>& shadow_maps,
        const ShadowSettings& shadow_settings,
        uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL
    );

    // Override from CxxFramePass
    void execute(ExecuteContext& ctx) override;

    std::vector<ResourceSpec> get_resource_specs() const override;

    // Compute read resources dynamically.
    std::set<const char*> compute_reads() const override;

    // Compute write resources dynamically.
    std::set<const char*> compute_writes() const override;

    /**
     * Get inplace aliases (input->output pairs that share the same FBO).
     */
    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const;

    /**
     * Add extra texture resource.
     * @param uniform_name Shader uniform name (will add u_ prefix if missing)
     * @param resource_name Framegraph resource name
     */
    void add_extra_texture(const std::string& uniform_name, const std::string& resource_name);

    /**
     * Get internal symbols for debugging.
     */
    std::vector<std::string> get_internal_symbols() const override {
        return entity_names;
    }

private:
    /**
     * Bind extra textures to texture units before rendering.
     */
    void bind_extra_textures(const FBOMap& reads_fbos);

    /**
     * Find camera component by entity name in scene.
     * Returns nullptr if not found.
     */
    CameraComponent* find_camera_by_name(tc_scene_handle scene, const std::string& name);

    // Cached camera lookup
    std::string cached_camera_name_;
    CameraComponent* cached_camera_ = nullptr;
    // Last GPU time in ms (from detailed profiling mode)
    double last_gpu_time_ms_ = 0.0;

    // Lighting UBO for efficient uniform uploads
    LightingUBO lighting_ubo_;

    // Cached draw calls vector (reused between frames to avoid allocations)
    std::vector<PhaseDrawCall> cached_draw_calls_;

    // Sort keys for distance sorting (parallel array to cached_draw_calls_)
    std::vector<uint64_t> sort_keys_;

    // Indices for sorting (reused between frames)
    std::vector<size_t> sort_indices_;

    // Temp buffer for sorted draw calls
    std::vector<PhaseDrawCall> sorted_draw_calls_;

    // Collect draw calls from scene entities into cached_draw_calls_.
    void collect_draw_calls(
        tc_scene_handle scene,
        const std::string& phase_mark,
        uint64_t layer_mask
    );

    // Compute sort keys for all draw calls (priority + distance)
    void compute_sort_keys(const Vec3& camera_position);

    // Sort draw calls by sort_keys_
    void sort_draw_calls();

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
