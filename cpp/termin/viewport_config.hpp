// viewport_config.hpp - C++ ViewportConfig class
#pragma once

#include <string>
#include <tuple>
#include <cstdint>

namespace termin {

// Configuration for mounting a scene viewport to a display
class ViewportConfig {
public:
    // Viewport name (used for scene pipeline targeting)
    std::string name;

    // Display name (RenderingManager will create/find display by this name)
    std::string display_name = "Main";

    // Camera entity UUID (looked up in scene during attach)
    std::string camera_uuid;

    // Normalized region on display (x, y, width, height)
    float region_x = 0.0f;
    float region_y = 0.0f;
    float region_w = 1.0f;
    float region_h = 1.0f;

    // Pipeline UUID (empty = use default or pipeline_name)
    std::string pipeline_uuid;

    // Pipeline name for special pipelines (e.g., "(Editor)")
    std::string pipeline_name;

    // Viewport depth (for ordering when multiple viewports on same display)
    int depth = 0;

    // Input mode for this viewport ("none", "simple", "editor")
    std::string input_mode = "simple";

    // Block input when running in editor mode
    bool block_input_in_editor = false;

    // Layer mask (which entity layers to render)
    uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL;

    // Whether this viewport is enabled for rendering
    bool enabled = true;

    // Default constructor
    ViewportConfig() = default;

    // Full constructor
    ViewportConfig(
        const std::string& name_,
        const std::string& display_name_,
        const std::string& camera_uuid_,
        float x, float y, float w, float h,
        const std::string& pipeline_uuid_,
        const std::string& pipeline_name_,
        int depth_,
        const std::string& input_mode_,
        bool block_input_in_editor_,
        uint64_t layer_mask_,
        bool enabled_
    ) : name(name_)
      , display_name(display_name_)
      , camera_uuid(camera_uuid_)
      , region_x(x)
      , region_y(y)
      , region_w(w)
      , region_h(h)
      , pipeline_uuid(pipeline_uuid_)
      , pipeline_name(pipeline_name_)
      , depth(depth_)
      , input_mode(input_mode_)
      , block_input_in_editor(block_input_in_editor_)
      , layer_mask(layer_mask_)
      , enabled(enabled_)
    {}

    // Region as tuple (for Python binding convenience)
    std::tuple<float, float, float, float> region() const {
        return {region_x, region_y, region_w, region_h};
    }

    void set_region(float x, float y, float w, float h) {
        region_x = x;
        region_y = y;
        region_w = w;
        region_h = h;
    }
};

} // namespace termin
