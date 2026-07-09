#pragma once

#include "termin/engine/termin_engine_api.hpp"
#include "termin/render/render_pipeline.hpp"
#include "termin/render/render_engine.hpp"

extern "C" {
#include "render/tc_display.h"
#include "render/tc_viewport.h"
#include "render/tc_viewport_pool.h"
#include "render/tc_render_surface.h"
}

#include <vector>
#include <memory>
#include <string>

namespace termin {

// PullRenderingManager - for pull-based rendering (WPF, Qt style)
// Each display's Render callback calls render_display() independently.
// Viewports are rendered to offscreen FBOs and immediately blitted to display.
class TERMIN_ENGINE_API PullRenderingManager {
public:
    RenderEngine* render_engine_ = nullptr;
    std::unique_ptr<RenderEngine> owned_render_engine_;
    std::vector<tc_display*> displays_;

    static PullRenderingManager* s_instance;

    static PullRenderingManager& instance();
    static void reset_for_testing();

    PullRenderingManager();
    ~PullRenderingManager();

    // Configuration
    void set_render_engine(RenderEngine* engine);
    RenderEngine* render_engine();

    // Display management
    void add_display(tc_display* display);
    void remove_display(tc_display* display);
    tc_display* get_display_by_name(const std::string& name) const;
    const std::vector<tc_display*>& displays() const { return displays_; }

    // Pull-rendering API
    // Renders this display's RT-backed viewports and blits them to display.
    // Call from each display's Render callback.
    void render_display(tc_display* display);

    // Shutdown
    void shutdown();

private:
    void render_viewport_offscreen(tc_viewport_handle viewport);
    std::vector<Light> collect_lights(tc_scene_handle scene);
};

} // namespace termin
