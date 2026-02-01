// rendering_manager.hpp - Global rendering manager singleton
//
// C++ port of Python's RenderingManager for unified rendering architecture.
// Manages displays, viewports, and offscreen-first rendering model.
//
// Offscreen-first rendering:
// 1. render_all_offscreen() - renders all viewports to their output_fbos
// 2. present_all() - blits output_fbos to displays
//
// Benefits:
// - Scene pipelines can span viewports on different displays
// - All GPU resources live in one context
// - Displays are independent and symmetrical
#pragma once

#include "termin/render/viewport_render_state.hpp"
#include "termin/render/render_pipeline.hpp"
#include "termin/render/render_engine.hpp"
#include "termin/render/graphics_backend.hpp"

extern "C" {
#include "tc_scene.h"
#include "render/tc_display.h"
#include "render/tc_viewport.h"
#include "render/tc_viewport_pool.h"
#include "render/tc_render_surface.h"
}

#include <vector>
#include <unordered_map>
#include <memory>
#include <functional>
#include <string>

namespace termin {

class CameraComponent;

// RenderingManager - Global singleton for managing displays and rendering
//
// Thread safety: NOT thread-safe. All calls must be from main/render thread.
class RenderingManager {
public:
    // Singleton access
    static RenderingManager& instance();
    static void reset_for_testing();

private:
    // Singleton
    RenderingManager();
    ~RenderingManager();
    RenderingManager(const RenderingManager&) = delete;
    RenderingManager& operator=(const RenderingManager&) = delete;

    static RenderingManager* s_instance;

public:
    // ========================================================================
    // Configuration
    // ========================================================================

    // Set graphics backend (required before rendering)
    void set_graphics(GraphicsBackend* graphics);
    GraphicsBackend* graphics() const { return graphics_; }

    // Set render engine (optional, created lazily if not set)
    void set_render_engine(RenderEngine* engine);
    RenderEngine* render_engine();

    // ========================================================================
    // Display Management
    // ========================================================================

    // Add display to management
    void add_display(tc_display* display);

    // Remove display from management
    void remove_display(tc_display* display);

    // Get all managed displays
    const std::vector<tc_display*>& displays() const { return displays_; }

    // Find display by name
    tc_display* get_display_by_name(const std::string& name) const;

    // ========================================================================
    // Viewport State Management
    // ========================================================================

    // Get render state for viewport (returns nullptr if not found)
    ViewportRenderState* get_viewport_state(tc_viewport_handle viewport);

    // Get or create render state for viewport
    ViewportRenderState* get_or_create_viewport_state(tc_viewport_handle viewport);

    // Remove viewport state (call when viewport is destroyed)
    void remove_viewport_state(tc_viewport_handle viewport);

    // ========================================================================
    // Rendering - Single Display (Simple Path)
    // ========================================================================

    // Render a single display (simple path for player/examples)
    // Renders all viewports on the display directly to screen.
    // void render_display(tc_display* display, bool present = true);

    // ========================================================================
    // Rendering - Offscreen-First Model (Full Path)
    // ========================================================================

    // Render all viewports using offscreen rendering model.
    // Phase 1: render_all_offscreen() - renders to output_fbos
    // Phase 2: present_all() - blits to displays
    void render_all(bool present = true);

    // Phase 1: Render all viewports to their output_fbos
    // All viewports (from all displays) rendered in single pass.
    void render_all_offscreen();

    // Phase 2: Blit viewport output_fbos to displays
    // For each display: make_current, clear, blit viewports, swap.
    void present_all();

    // ========================================================================
    // Scene Pipeline Management
    // ========================================================================

    // Register a compiled scene pipeline for a scene
    void add_scene_pipeline(tc_scene_handle scene, const std::string& name, RenderPipeline* pipeline);

    // Unregister a scene pipeline
    void remove_scene_pipeline(tc_scene_handle scene, const std::string& name);

    // Get scene pipeline by name (searches in specific scene)
    RenderPipeline* get_scene_pipeline(tc_scene_handle scene, const std::string& name) const;

    // Get scene pipeline by name (searches all scenes)
    RenderPipeline* get_scene_pipeline(const std::string& name) const;

    // Clear all pipelines for a scene
    void clear_scene_pipelines(tc_scene_handle scene);

    // Clear all scene pipelines
    void clear_all_scene_pipelines();

    // ========================================================================
    // Shutdown
    // ========================================================================

    // Cleanup all resources
    void shutdown();

private:
    // Render single viewport to its output FBO
    void render_viewport_offscreen(tc_viewport_handle viewport);

    // Blit viewports to single display
    void present_display(tc_display* display);

    // Collect lights from scene (simplified - returns empty for now)
    std::vector<Light> collect_lights(tc_scene_handle scene);

private:
    // Managed displays
    std::vector<tc_display*> displays_;

    // Viewport render states (key = viewport handle as uint64)
    std::unordered_map<uint64_t, std::unique_ptr<ViewportRenderState>> viewport_states_;

    // Graphics backend (not owned)
    GraphicsBackend* graphics_ = nullptr;

    // Render engine (owned if created internally)
    RenderEngine* render_engine_ = nullptr;
    std::unique_ptr<RenderEngine> owned_render_engine_;

    // Scene pipelines: scene_handle -> (pipeline_name -> pipeline)
    // Key is (scene.index << 32 | scene.generation)
    std::unordered_map<uint64_t, std::unordered_map<std::string, RenderPipeline*>> scene_pipelines_;

    // Helper to make key from scene handle
    static uint64_t scene_key(tc_scene_handle h) {
        return (static_cast<uint64_t>(h.index) << 32) | h.generation;
    }
};

} // namespace termin
