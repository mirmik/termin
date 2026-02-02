// pull_rendering_manager.cpp - Pull-based rendering manager for WPF/Qt style rendering

#include "termin/render/pull_rendering_manager.hpp"
#include "termin/camera/camera_component.hpp"

extern "C" {
#include "tc_log.h"
#include "render/tc_viewport_pool.h"
}

#include <algorithm>

namespace termin {

// Helper to make a unique key from viewport handle
static inline uint64_t viewport_key(tc_viewport_handle h) {
    return (static_cast<uint64_t>(h.index) << 32) | h.generation;
}

// Singleton
PullRenderingManager* PullRenderingManager::s_instance = nullptr;

PullRenderingManager& PullRenderingManager::instance() {
    if (!s_instance) {
        s_instance = new PullRenderingManager();
    }
    return *s_instance;
}

void PullRenderingManager::reset_for_testing() {
    if (s_instance) {
        delete s_instance;
        s_instance = nullptr;
    }
}

PullRenderingManager::PullRenderingManager() = default;

PullRenderingManager::~PullRenderingManager() {
    shutdown();
}

// Configuration
void PullRenderingManager::set_graphics(GraphicsBackend* graphics) {
    graphics_ = graphics;
}

void PullRenderingManager::set_render_engine(RenderEngine* engine) {
    render_engine_ = engine;
    owned_render_engine_.reset();
}

RenderEngine* PullRenderingManager::render_engine() {
    if (!render_engine_) {
        if (!graphics_) {
            tc_log(TC_LOG_ERROR, "[PullRenderingManager] Cannot create RenderEngine: graphics not set");
            return nullptr;
        }
        owned_render_engine_ = std::make_unique<RenderEngine>(graphics_);
        render_engine_ = owned_render_engine_.get();
    }
    return render_engine_;
}

// Display management
void PullRenderingManager::add_display(tc_display* display) {
    if (!display) return;

    auto it = std::find(displays_.begin(), displays_.end(), display);
    if (it != displays_.end()) return;

    displays_.push_back(display);
    tc_log(TC_LOG_INFO, "[PullRenderingManager] Added display: %s",
           tc_display_get_name(display) ? tc_display_get_name(display) : "(unnamed)");
}

void PullRenderingManager::remove_display(tc_display* display) {
    if (!display) return;

    auto it = std::find(displays_.begin(), displays_.end(), display);
    if (it == displays_.end()) return;

    // Clean up viewport states for viewports on this display
    tc_viewport_handle vp = tc_display_get_first_viewport(display);
    while (tc_viewport_handle_valid(vp)) {
        remove_viewport_state(vp);
        vp = tc_viewport_get_display_next(vp);
    }

    displays_.erase(it);
    tc_log(TC_LOG_INFO, "[PullRenderingManager] Removed display: %s",
           tc_display_get_name(display) ? tc_display_get_name(display) : "(unnamed)");
}

tc_display* PullRenderingManager::get_display_by_name(const std::string& name) const {
    for (tc_display* d : displays_) {
        const char* dname = tc_display_get_name(d);
        if (dname && name == dname) {
            return d;
        }
    }
    return nullptr;
}

// Viewport state management
ViewportRenderState* PullRenderingManager::get_viewport_state(tc_viewport_handle viewport) {
    if (!tc_viewport_handle_valid(viewport)) return nullptr;
    uint64_t key = viewport_key(viewport);
    auto it = viewport_states_.find(key);
    return (it != viewport_states_.end()) ? it->second.get() : nullptr;
}

ViewportRenderState* PullRenderingManager::get_or_create_viewport_state(tc_viewport_handle viewport) {
    if (!tc_viewport_handle_valid(viewport)) return nullptr;
    uint64_t key = viewport_key(viewport);
    auto& state = viewport_states_[key];
    if (!state) {
        state = std::make_unique<ViewportRenderState>();
    }
    return state.get();
}

void PullRenderingManager::remove_viewport_state(tc_viewport_handle viewport) {
    if (!tc_viewport_handle_valid(viewport)) return;
    uint64_t key = viewport_key(viewport);
    auto it = viewport_states_.find(key);
    if (it != viewport_states_.end()) {
        it->second->clear_all();
        viewport_states_.erase(it);
    }
}

// Pull-rendering: render and present single display
void PullRenderingManager::render_display(tc_display* display) {
    if (!display || !graphics_) return;

    const char* dname = tc_display_get_name(display);

    tc_render_surface* surface = tc_display_get_surface(display);
    if (!surface) {
        tc_log(TC_LOG_WARN, "[PullRenderingManager] render_display: surface is null");
        return;
    }

    // Make display context current
    tc_render_surface_make_current(surface);

    int width, height;
    tc_render_surface_get_size(surface, &width, &height);
    if (width <= 0 || height <= 0) return;

    uint32_t display_fbo = tc_render_surface_get_framebuffer(surface);

    // Clear display
    graphics_->bind_framebuffer_id(display_fbo);
    graphics_->set_viewport(0, 0, width, height);
    graphics_->clear_color_depth({0.1f, 0.1f, 0.1f, 1.0f});

    // Collect viewports sorted by depth
    std::vector<tc_viewport_handle> viewports;
    tc_viewport_handle vp = tc_display_get_first_viewport(display);
    while (tc_viewport_handle_valid(vp)) {
        if (tc_viewport_get_enabled(vp)) {
            viewports.push_back(vp);
        }
        vp = tc_viewport_get_display_next(vp);
    }
    std::sort(viewports.begin(), viewports.end(), [](tc_viewport_handle a, tc_viewport_handle b) {
        return tc_viewport_get_depth(a) < tc_viewport_get_depth(b);
    });

    // Render and blit each viewport
    for (tc_viewport_handle viewport : viewports) {
        // Skip viewports managed by scene pipeline
        const char* managed_by = tc_viewport_get_managed_by(viewport);
        if (managed_by && managed_by[0] != '\0') continue;

        // Update viewport pixel_rect based on current display size
        tc_viewport_update_pixel_rect(viewport, width, height);

        // Render viewport to offscreen FBO
        render_viewport_offscreen(viewport);

        // Blit to display
        ViewportRenderState* state = get_viewport_state(viewport);
        if (!state || !state->has_output_fbo()) {
            tc_log(TC_LOG_WARN, "[PullRM] viewport has no output_fbo after render");
            continue;
        }

        int px, py, pw, ph;
        tc_viewport_get_pixel_rect(viewport, &px, &py, &pw, &ph);

        int src_w = state->output_width;
        int src_h = state->output_height;

        graphics_->blit_framebuffer_to_id(
            *state->output_fbo,
            display_fbo,
            {0, 0, src_w, src_h},
            {px, py, px + pw, py + ph}
        );
    }
}

void PullRenderingManager::render_viewport_offscreen(tc_viewport_handle viewport) {
    if (!tc_viewport_handle_valid(viewport) || !graphics_) return;

    tc_scene_handle scene = tc_viewport_get_scene(viewport);
    tc_component* camera_comp = tc_viewport_get_camera(viewport);
    tc_pipeline_handle pipeline = tc_viewport_get_pipeline(viewport);

    if (!tc_scene_handle_valid(scene) || !camera_comp || !tc_pipeline_handle_valid(pipeline)) {
        tc_log(TC_LOG_WARN, "[PullRM] viewport missing scene/camera/pipeline");
        return;
    }

    RenderPipeline* render_pipeline = RenderPipeline::from_handle(pipeline);
    if (!render_pipeline) return;

    CxxComponent* cxx = CxxComponent::from_tc(camera_comp);
    CameraComponent* camera = cxx ? static_cast<CameraComponent*>(cxx) : nullptr;
    if (!camera) return;

    int px, py, pw, ph;
    tc_viewport_get_pixel_rect(viewport, &px, &py, &pw, &ph);
    if (pw <= 0 || ph <= 0) return;

    ViewportRenderState* state = get_or_create_viewport_state(viewport);
    FramebufferHandle* output_fbo = state->ensure_output_fbo(graphics_, pw, ph);

    std::vector<Light> lights = collect_lights(scene);

    RenderEngine* engine = render_engine();
    engine->render_view_to_fbo(
        render_pipeline,
        output_fbo,
        pw, ph,
        scene,
        camera,
        viewport,
        lights,
        tc_viewport_get_layer_mask(viewport)
    );
}

// Shutdown
void PullRenderingManager::shutdown() {
    for (auto& pair : viewport_states_) {
        pair.second->clear_all();
    }
    viewport_states_.clear();
    displays_.clear();
    owned_render_engine_.reset();
    render_engine_ = nullptr;
    graphics_ = nullptr;
}

// Helpers
std::vector<Light> PullRenderingManager::collect_lights(tc_scene_handle scene) {
    return {};
}

} // namespace termin
