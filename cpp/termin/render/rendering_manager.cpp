// rendering_manager.cpp - Global rendering manager implementation
#include "termin/render/rendering_manager.hpp"
#include "termin/camera/camera_component.hpp"

extern "C" {
#include "tc_log.h"
}

#include <algorithm>

namespace termin {

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
    tc_viewport* vp = tc_display_get_first_viewport(display);
    while (vp) {
        remove_viewport_state(vp);
        vp = vp->display_next;
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

ViewportRenderState* RenderingManager::get_viewport_state(tc_viewport* viewport) {
    if (!viewport) return nullptr;
    uintptr_t key = reinterpret_cast<uintptr_t>(viewport);
    auto it = viewport_states_.find(key);
    return (it != viewport_states_.end()) ? it->second.get() : nullptr;
}

ViewportRenderState* RenderingManager::get_or_create_viewport_state(tc_viewport* viewport) {
    if (!viewport) return nullptr;
    uintptr_t key = reinterpret_cast<uintptr_t>(viewport);
    auto& state = viewport_states_[key];
    if (!state) {
        state = std::make_unique<ViewportRenderState>();
    }
    return state.get();
}

void RenderingManager::remove_viewport_state(tc_viewport* viewport) {
    if (!viewport) return;
    uintptr_t key = reinterpret_cast<uintptr_t>(viewport);
    auto it = viewport_states_.find(key);
    if (it != viewport_states_.end()) {
        it->second->clear_all();
        viewport_states_.erase(it);
    }
}

// ============================================================================
// Rendering - Single Display
// ============================================================================

// void RenderingManager::render_display(tc_display* display, bool present) {
//     if (!display) return;
//     if (!graphics_) {
//         tc_log(TC_LOG_WARN, "[RenderingManager] render_display: graphics not set");
//         return;
//     }

//     RenderEngine* engine = render_engine();
//     if (!engine) return;

//     tc_render_surface* surface = tc_display_get_surface(display);
//     if (!surface) {
//         tc_log(TC_LOG_WARN, "[RenderingManager] render_display: surface is null");
//         return;
//     }

//     int width, height;
//     tc_render_surface_get_size(surface, &width, &height);
//     if (width <= 0 || height <= 0) return;

//     // Collect viewports sorted by depth
//     std::vector<tc_viewport*> viewports;
//     tc_viewport* vp = tc_display_get_first_viewport(display);
//     while (vp) {
//         if (tc_viewport_get_enabled(vp)) {
//             viewports.push_back(vp);
//         }
//         vp = vp->display_next;
//     }
//     std::sort(viewports.begin(), viewports.end(), [](tc_viewport* a, tc_viewport* b) {
//         return tc_viewport_get_depth(a) < tc_viewport_get_depth(b);
//     });

//     // Get display framebuffer
//     uint32_t display_fbo = tc_render_surface_get_framebuffer(surface);

//     // Clear display
//     graphics_->bind_framebuffer_id(display_fbo);
//     graphics_->set_viewport(0, 0, width, height);
//     graphics_->clear_color_depth({0.1f, 0.1f, 0.1f, 1.0f});

//     // Render each viewport
//     for (tc_viewport* viewport : viewports) {
//         tc_scene* scene = tc_viewport_get_scene(viewport);
//         tc_component* camera_comp = tc_viewport_get_camera(viewport);
//         tc_pipeline* pipeline = tc_viewport_get_pipeline(viewport);

//         if (!scene || !camera_comp || !pipeline) continue;

//         // Get RenderPipeline from tc_pipeline
//         RenderPipeline* render_pipeline = RenderPipeline::from_tc_pipeline(pipeline);
//         if (!render_pipeline) continue;

//         // Get CameraComponent
//         CameraComponent* camera = static_cast<CameraComponent*>(camera_comp->body);
//         if (!camera) continue;

//         // Get pixel rect
//         int px, py, pw, ph;
//         tc_viewport_get_pixel_rect(viewport, &px, &py, &pw, &ph);
//         if (pw <= 0 || ph <= 0) continue;

//         // Collect lights (simplified)
//         std::vector<Light> lights = collect_lights(scene);

//         // Render viewport
//         engine->render_view_to_fbo(
//             render_pipeline,
//             nullptr,  // target_fbo = nullptr means use pipeline's color FBO
//             pw, ph,
//             scene,
//             camera,
//             viewport,
//             lights,
//             tc_viewport_get_layer_mask(viewport)
//         );

//         // Blit pipeline's color FBO to display at viewport position
//         FramebufferHandle* color_fbo = render_pipeline->get_fbo("color");
//         if (color_fbo && color_fbo->get_fbo_id() != 0) {
//             graphics_->blit_framebuffer_to_id(
//                 *color_fbo,
//                 display_fbo,
//                 {0, 0, pw, ph},
//                 {px, py, px + pw, py + ph}
//             );
//         }
//     }

//     // Swap buffers
//     if (present) {
//         tc_render_surface_swap_buffers(surface);
//     }
// }

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

    tc_log(TC_LOG_INFO, "[RenderingManager] render_all_offscreen: %zu displays", displays_.size());

    // Render all viewports from all displays
    for (tc_display* display : displays_) {
        // Make display context current before rendering its viewports
        tc_render_surface* surface = tc_display_get_surface(display);
        if (surface) {
            tc_render_surface_make_current(surface);
        }

        tc_viewport* vp = tc_display_get_first_viewport(display);
        int vp_count = 0;
        while (vp) {
            vp_count++;
            if (tc_viewport_get_enabled(vp)) {
                // Skip viewports managed by scene pipeline
                const char* managed_by = tc_viewport_get_managed_by(vp);
                if (!managed_by || managed_by[0] == '\0') {
                    tc_log(TC_LOG_INFO, "[RenderingManager] rendering viewport '%s'",
                        vp->name ? vp->name : "(null)");
                    render_viewport_offscreen(vp);
                }
            }
            vp = vp->display_next;
        }
        tc_log(TC_LOG_INFO, "[RenderingManager] display has %d viewports", vp_count);
    }
}

void RenderingManager::render_viewport_offscreen(tc_viewport* viewport) {
    if (!viewport || !graphics_) return;

    tc_scene* scene = tc_viewport_get_scene(viewport);
    tc_component* camera_comp = tc_viewport_get_camera(viewport);
    tc_pipeline* pipeline = tc_viewport_get_pipeline(viewport);

    if (!scene || !camera_comp || !pipeline) return;

    // Get RenderPipeline from tc_pipeline
    RenderPipeline* render_pipeline = RenderPipeline::from_tc_pipeline(pipeline);
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

    tc_log(TC_LOG_INFO, "[RenderingManager] render_viewport_offscreen: output_fbo=%u (%dx%d)",
        output_fbo ? output_fbo->get_fbo_id() : 0, pw, ph);

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

    // Debug: read center pixel to check if anything was rendered
    auto pixel = graphics_->read_pixel(output_fbo, pw/2, ph/2);
    tc_log(TC_LOG_INFO, "[RenderingManager] output_fbo center pixel: (%.2f, %.2f, %.2f, %.2f)",
        pixel[0], pixel[1], pixel[2], pixel[3]);
}

void RenderingManager::present_all() {
    for (tc_display* display : displays_) {
        present_display(display);
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
    std::vector<tc_viewport*> viewports;
    tc_viewport* vp = tc_display_get_first_viewport(display);
    while (vp) {
        if (tc_viewport_get_enabled(vp)) {
            viewports.push_back(vp);
        }
        vp = vp->display_next;
    }
    std::sort(viewports.begin(), viewports.end(), [](tc_viewport* a, tc_viewport* b) {
        return tc_viewport_get_depth(a) < tc_viewport_get_depth(b);
    });

    tc_log(TC_LOG_INFO, "[RenderingManager] present_display: %zu viewports to blit", viewports.size());

    // Blit viewports
    for (tc_viewport* viewport : viewports) {
        ViewportRenderState* state = get_viewport_state(viewport);
        if (!state || !state->has_output_fbo()) {
            tc_log(TC_LOG_WARN, "[RenderingManager] viewport '%s' has no output_fbo (state=%p)",
                viewport->name ? viewport->name : "(null)", (void*)state);
            continue;
        }

        // Get viewport position on display
        int px, py, pw, ph;
        tc_viewport_get_pixel_rect(viewport, &px, &py, &pw, &ph);

        // Get output FBO size
        int src_w = state->output_width;
        int src_h = state->output_height;

        tc_log(TC_LOG_INFO, "[RenderingManager] blit: src_fbo=%u (%dx%d) -> dst_fbo=%u at (%d,%d,%d,%d)",
            state->output_fbo->get_fbo_id(), src_w, src_h,
            display_fbo, px, py, px + pw, py + ph);

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
// Shutdown
// ============================================================================

void RenderingManager::shutdown() {
    // Clear viewport states
    for (auto& pair : viewport_states_) {
        pair.second->clear_all();
    }
    viewport_states_.clear();

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

std::vector<Light> RenderingManager::collect_lights(tc_scene* scene) {
    // TODO: Implement proper light collection from scene
    // For now, return empty - ambient lighting only
    return {};
}

} // namespace termin
