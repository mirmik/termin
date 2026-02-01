// rendering_manager.cpp - Global rendering manager implementation
#include "termin/render/rendering_manager.hpp"
#include "termin/camera/camera_component.hpp"

extern "C" {
#include "tc_log.h"
#include "tc_scene.h"
#include "render/tc_viewport_pool.h"
}

#include <algorithm>

namespace termin {

// Helper to make a unique key from viewport handle
static inline uint64_t viewport_key(tc_viewport_handle h) {
    return (static_cast<uint64_t>(h.index) << 32) | h.generation;
}

// ============================================================================
// Singleton
// ============================================================================

RenderingManager* RenderingManager::s_instance = nullptr;

RenderingManager& RenderingManager::instance() {
    if (!s_instance) {
        s_instance = new RenderingManager();
    }
    return *s_instance;
}

void RenderingManager::reset_for_testing() {
    if (s_instance) {
        delete s_instance;
        s_instance = nullptr;
    }
}

RenderingManager::RenderingManager() = default;

RenderingManager::~RenderingManager() {
    shutdown();
}

// ============================================================================
// Configuration
// ============================================================================

void RenderingManager::set_graphics(GraphicsBackend* graphics) {
    graphics_ = graphics;
}

void RenderingManager::set_render_engine(RenderEngine* engine) {
    render_engine_ = engine;
    owned_render_engine_.reset(); // Release owned engine if any
}

RenderEngine* RenderingManager::render_engine() {
    if (!render_engine_) {
        if (!graphics_) {
            tc_log(TC_LOG_ERROR, "[RenderingManager] Cannot create RenderEngine: graphics not set");
            return nullptr;
        }
        owned_render_engine_ = std::make_unique<RenderEngine>(graphics_);
        render_engine_ = owned_render_engine_.get();
    }
    return render_engine_;
}

// ============================================================================
// Display Management
// ============================================================================

void RenderingManager::add_display(tc_display* display) {
    if (!display) return;

    // Check if already managed
    auto it = std::find(displays_.begin(), displays_.end(), display);
    if (it != displays_.end()) return;

    displays_.push_back(display);
    tc_log(TC_LOG_INFO, "[RenderingManager] Added display: %s",
           tc_display_get_name(display) ? tc_display_get_name(display) : "(unnamed)");
}

void RenderingManager::remove_display(tc_display* display) {
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
    tc_log(TC_LOG_INFO, "[RenderingManager] Removed display: %s",
           tc_display_get_name(display) ? tc_display_get_name(display) : "(unnamed)");
}

tc_display* RenderingManager::get_display_by_name(const std::string& name) const {
    for (tc_display* d : displays_) {
        const char* dname = tc_display_get_name(d);
        if (dname && name == dname) {
            return d;
        }
    }
    return nullptr;
}

// ============================================================================
// Viewport State Management
// ============================================================================

ViewportRenderState* RenderingManager::get_viewport_state(tc_viewport_handle viewport) {
    if (!tc_viewport_handle_valid(viewport)) return nullptr;
    uint64_t key = viewport_key(viewport);
    auto it = viewport_states_.find(key);
    return (it != viewport_states_.end()) ? it->second.get() : nullptr;
}

ViewportRenderState* RenderingManager::get_or_create_viewport_state(tc_viewport_handle viewport) {
    if (!tc_viewport_handle_valid(viewport)) return nullptr;
    uint64_t key = viewport_key(viewport);
    auto& state = viewport_states_[key];
    if (!state) {
        state = std::make_unique<ViewportRenderState>();
    }
    return state.get();
}

void RenderingManager::remove_viewport_state(tc_viewport_handle viewport) {
    if (!tc_viewport_handle_valid(viewport)) return;
    uint64_t key = viewport_key(viewport);
    auto it = viewport_states_.find(key);
    if (it != viewport_states_.end()) {
        it->second->clear_all();
        viewport_states_.erase(it);
    }
}

// ============================================================================
// Rendering - Offscreen-First Model
// ============================================================================

void RenderingManager::render_all(bool present) {
    render_all_offscreen();
    if (present) {
        present_all();
    }
}

void RenderingManager::render_all_offscreen() {
    if (!graphics_) {
        tc_log(TC_LOG_WARN, "[RenderingManager] render_all_offscreen: graphics not set");
        return;
    }

    RenderEngine* engine = render_engine();
    if (!engine) {
        tc_log(TC_LOG_WARN, "[RenderingManager] render_all_offscreen: no render engine");
        return;
    }

    // Render all viewports from all displays
    for (tc_display* display : displays_) {
        // Skip disabled displays
        if (!tc_display_get_enabled(display)) {
            continue;
        }

        // Make display context current before rendering its viewports
        tc_render_surface* surface = tc_display_get_surface(display);
        if (surface) {
            tc_render_surface_make_current(surface);
        }

        tc_viewport_handle vp = tc_display_get_first_viewport(display);
        while (tc_viewport_handle_valid(vp)) {
            if (tc_viewport_get_enabled(vp)) {
                // Skip viewports managed by scene pipeline
                const char* managed_by = tc_viewport_get_managed_by(vp);
                if (!managed_by || managed_by[0] == '\0') {
                    render_viewport_offscreen(vp);
                }
            }
            vp = tc_viewport_get_display_next(vp);
        }
    }
}

void RenderingManager::render_viewport_offscreen(tc_viewport_handle viewport) {
    if (!tc_viewport_handle_valid(viewport) || !graphics_) return;

    tc_scene_handle scene = tc_viewport_get_scene(viewport);
    tc_component* camera_comp = tc_viewport_get_camera(viewport);
    tc_pipeline_handle pipeline = tc_viewport_get_pipeline(viewport);

    if (!tc_scene_handle_valid(scene) || !camera_comp || !tc_pipeline_handle_valid(pipeline)) return;

    // Get RenderPipeline from pipeline handle
    RenderPipeline* render_pipeline = RenderPipeline::from_handle(pipeline);
    if (!render_pipeline) return;

    // Get CameraComponent from tc_component using container_of pattern
    CxxComponent* cxx = CxxComponent::from_tc(camera_comp);
    CameraComponent* camera = cxx ? static_cast<CameraComponent*>(cxx) : nullptr;
    if (!camera) return;

    // Get pixel rect
    int px, py, pw, ph;
    tc_viewport_get_pixel_rect(viewport, &px, &py, &pw, &ph);
    if (pw <= 0 || ph <= 0) return;

    // Ensure output FBO
    ViewportRenderState* state = get_or_create_viewport_state(viewport);
    FramebufferHandle* output_fbo = state->ensure_output_fbo(graphics_, pw, ph);

    // Collect lights
    std::vector<Light> lights = collect_lights(scene);

    // Render to output FBO
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

void RenderingManager::present_all() {
    for (tc_display* display : displays_) {
        if (tc_display_get_enabled(display)) {
            present_display(display);
        }
    }
}

void RenderingManager::present_display(tc_display* display) {
    if (!display || !graphics_) return;

    tc_render_surface* surface = tc_display_get_surface(display);
    if (!surface) {
        tc_log(TC_LOG_WARN, "[RenderingManager] present_display: surface is null");
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

    // Blit viewports
    for (tc_viewport_handle viewport : viewports) {
        ViewportRenderState* state = get_viewport_state(viewport);
        if (!state || !state->has_output_fbo()) continue;

        // Get viewport position on display
        int px, py, pw, ph;
        tc_viewport_get_pixel_rect(viewport, &px, &py, &pw, &ph);

        // Get output FBO size
        int src_w = state->output_width;
        int src_h = state->output_height;

        // Blit output_fbo → display_fbo
        graphics_->blit_framebuffer_to_id(
            *state->output_fbo,
            display_fbo,
            {0, 0, src_w, src_h},
            {px, py, px + pw, py + ph}
        );
    }

    // Swap buffers
    tc_render_surface_swap_buffers(surface);
}

// ============================================================================
// Scene Pipeline Management
// ============================================================================

void RenderingManager::add_scene_pipeline(tc_scene_handle scene, const std::string& name, RenderPipeline* pipeline) {
    if (!tc_scene_handle_valid(scene) || name.empty() || !pipeline) return;
    uint64_t key = scene_key(scene);
    scene_pipelines_[key][name] = pipeline;
}

void RenderingManager::remove_scene_pipeline(tc_scene_handle scene, const std::string& name) {
    if (!tc_scene_handle_valid(scene)) return;
    uint64_t key = scene_key(scene);
    auto it = scene_pipelines_.find(key);
    if (it != scene_pipelines_.end()) {
        it->second.erase(name);
    }
}

RenderPipeline* RenderingManager::get_scene_pipeline(tc_scene_handle scene, const std::string& name) const {
    if (!tc_scene_handle_valid(scene)) return nullptr;
    uint64_t key = scene_key(scene);
    auto scene_it = scene_pipelines_.find(key);
    if (scene_it == scene_pipelines_.end()) return nullptr;
    auto pipe_it = scene_it->second.find(name);
    return (pipe_it != scene_it->second.end()) ? pipe_it->second : nullptr;
}

RenderPipeline* RenderingManager::get_scene_pipeline(const std::string& name) const {
    // Search all scenes
    for (const auto& [scene_key, pipelines] : scene_pipelines_) {
        auto it = pipelines.find(name);
        if (it != pipelines.end()) {
            return it->second;
        }
    }
    return nullptr;
}

void RenderingManager::set_pipeline_targets(const std::string& pipeline_name, const std::vector<std::string>& targets) {
    pipeline_targets_[pipeline_name] = targets;
}

static const std::vector<std::string> empty_targets;

const std::vector<std::string>& RenderingManager::get_pipeline_targets(const std::string& pipeline_name) const {
    auto it = pipeline_targets_.find(pipeline_name);
    return (it != pipeline_targets_.end()) ? it->second : empty_targets;
}

std::vector<std::string> RenderingManager::get_pipeline_names(tc_scene_handle scene) const {
    std::vector<std::string> names;
    if (!tc_scene_handle_valid(scene)) return names;

    uint64_t key = scene_key(scene);
    auto scene_it = scene_pipelines_.find(key);
    if (scene_it != scene_pipelines_.end()) {
        for (const auto& [name, _] : scene_it->second) {
            names.push_back(name);
        }
    }
    return names;
}

void RenderingManager::clear_scene_pipelines(tc_scene_handle scene) {
    if (!tc_scene_handle_valid(scene)) return;
    uint64_t key = scene_key(scene);

    // Remove pipeline targets for this scene's pipelines
    auto scene_it = scene_pipelines_.find(key);
    if (scene_it != scene_pipelines_.end()) {
        for (const auto& [name, _] : scene_it->second) {
            pipeline_targets_.erase(name);
        }
    }

    scene_pipelines_.erase(key);
}

void RenderingManager::clear_all_scene_pipelines() {
    scene_pipelines_.clear();
}

// ============================================================================
// Shutdown
// ============================================================================

void RenderingManager::shutdown() {
    // Clear viewport states
    for (auto& pair : viewport_states_) {
        pair.second->clear_all();
    }
    viewport_states_.clear();

    // Clear scene pipelines (we don't own them)
    clear_all_scene_pipelines();

    // Clear displays (don't free them - we don't own them)
    displays_.clear();

    // Release owned render engine
    owned_render_engine_.reset();
    render_engine_ = nullptr;

    graphics_ = nullptr;
}

// ============================================================================
// Helpers
// ============================================================================

std::vector<Light> RenderingManager::collect_lights(tc_scene_handle scene) {
    // TODO: Implement proper light collection from scene
    // For now, return empty - ambient lighting only
    return {};
}

} // namespace termin
