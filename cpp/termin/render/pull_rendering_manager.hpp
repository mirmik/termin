#pragma once

#include "termin/render/viewport_render_state.hpp"
#include "termin/render/render_pipeline.hpp"
#include "termin/render/render_engine.hpp"
#include "tgfx/graphics_backend.hpp"

extern "C" {
#include "render/tc_display.h"
#include "render/tc_viewport.h"
#include "render/tc_viewport_pool.h"
#include "render/tc_render_surface.h"
}

#include <vector>
#include <unordered_map>
#include <memory>
#include <string>

namespace termin {

// PullRenderingManager - for pull-based rendering (WPF, Qt style)
// Each display's Render callback calls render_display() independently.
// Viewports are rendered to offscreen FBOs and immediately blitted to display.
class PullRenderingManager {
public:
    GraphicsBackend* graphics_ = nullptr;
    RenderEngine* render_engine_ = nullptr;
    std::unique_ptr<RenderEngine> owned_render_engine_;
    std::vector<tc_display*> displays_;
    std::unordered_map<uint64_t, std::unique_ptr<ViewportRenderState>> viewport_states_;

    static PullRenderingManager* s_instance;

    static PullRenderingManager& instance();
    static void reset_for_testing();

    PullRenderingManager();
    ~PullRenderingManager();

    // Configuration
    void set_graphics(GraphicsBackend* graphics);
    void set_render_engine(RenderEngine* engine);
    RenderEngine* render_engine();

    // Display management
    void add_display(tc_display* display);
    void remove_display(tc_display* display);
    tc_display* get_display_by_name(const std::string& name) const;
    const std::vector<tc_display*>& displays() const { return displays_; }

    // Viewport state management
    ViewportRenderState* get_viewport_state(tc_viewport_handle viewport);
    ViewportRenderState* get_or_create_viewport_state(tc_viewport_handle viewport);
    void remove_viewport_state(tc_viewport_handle viewport);

    // Pull-rendering API
    // Renders all viewports of this display to offscreen FBOs and blits to display.
    // Call from each display's Render callback.
    void render_display(tc_display* display);

    // Shutdown
    void shutdown();

private:
    void render_viewport_offscreen(tc_viewport_handle viewport);
    std::vector<Light> collect_lights(tc_scene_handle scene);
};

} // namespace termin
