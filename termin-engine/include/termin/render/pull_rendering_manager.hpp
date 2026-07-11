#pragma once

#include "termin/engine/termin_engine_api.hpp"
#include "termin/render/rendering_manager.hpp"
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

// PullRenderingManager - deprecated compatibility wrapper for pull-based hosts.
// Each display's Render callback calls render_display() independently.
// Viewports are rendered to offscreen FBOs and immediately blitted to display.
#if defined(_MSC_VER)
#define TERMIN_PULL_RENDERING_MANAGER_DEPRECATED __declspec(deprecated("Use RenderingManager::render_display(tc_display*) instead."))
#else
#define TERMIN_PULL_RENDERING_MANAGER_DEPRECATED [[deprecated("Use RenderingManager::render_display(tc_display*) instead.")]]
#endif

class TERMIN_ENGINE_API TERMIN_PULL_RENDERING_MANAGER_DEPRECATED PullRenderingManager {
public:
    static PullRenderingManager* s_instance;

private:
    std::unique_ptr<RenderingManager> owned_manager_;
    RenderingManager* manager_ = nullptr;

public:
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
    const std::vector<tc_display*>& displays() const;

    // Pull-rendering API
    // Renders this display's RT-backed viewports and blits them to display.
    // Call from each display's Render callback.
    void render_display(tc_display* display);

    // Shutdown
    void shutdown();

private:
    RenderingManager* manager();

};

#undef TERMIN_PULL_RENDERING_MANAGER_DEPRECATED

} // namespace termin
