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
#include "core/tc_scene.h"
#include "tc_viewport_config.h"
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

// Factory callback types
using DisplayFactory = std::function<tc_display*(const std::string& name)>;
using PipelineFactory = std::function<RenderPipeline*(const std::string& name)>;
using MakeCurrentCallback = std::function<void()>;

// RenderingManager - manages displays and rendering
//
// Owned by EngineCore. Global instance() returns the one set by EngineCore.
// Thread safety: NOT thread-safe. All calls must be from main/render thread.
class RenderingManager {
public:
    // Global instance access (set by EngineCore)
    static RenderingManager& instance();
    static void set_instance(RenderingManager* instance);
    static void reset_for_testing();

    RenderingManager();
    ~RenderingManager();

private:
    // Disable copy
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

    // Set callback to activate GL context before rendering
    void set_make_current_callback(MakeCurrentCallback callback);

    // Set factory for creating displays on demand
    void set_display_factory(DisplayFactory factory);

    // Set factory for creating pipelines by special name (e.g., "(Editor)")
    void set_pipeline_factory(PipelineFactory factory);

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

    // Get existing display or create via factory
    tc_display* get_or_create_display(const std::string& name);

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
    // Scene Mounting
    // ========================================================================

    // Mount scene to display region, creating a viewport
    // Returns viewport handle (invalid if failed)
    tc_viewport_handle mount_scene(
        tc_scene_handle scene,
        tc_display* display,
        CameraComponent* camera,
        float region_x, float region_y, float region_w, float region_h,
        RenderPipeline* pipeline,
        const std::string& name
    );

    // Unmount scene from display (removes all viewports showing this scene)
    void unmount_scene(tc_scene_handle scene, tc_display* display);

    // Attach scene using its viewport_configs
    // Creates displays via factory, mounts viewports, compiles scene pipelines
    // Returns list of created viewport handles
    std::vector<tc_viewport_handle> attach_scene_full(tc_scene_handle scene);

    // Detach scene from all displays and cleanup
    void detach_scene_full(tc_scene_handle scene);

    // Get attached scenes list
    const std::vector<tc_scene_handle>& attached_scenes() const { return attached_scenes_; }

    // ========================================================================
    // Scene Pipeline Management
    // ========================================================================

    // Attach scene pipelines only - compiles pipeline templates stored in tc_scene
    // Called by attach_scene_full. Notifies components via on_render_attach.
    void attach_scene(tc_scene_handle scene);

    // Detach scene from rendering - destroys compiled pipelines
    // Called when scene is unmounted. Notifies components via on_render_detach.
    void detach_scene(tc_scene_handle scene);

    // Get scene pipeline by name (searches in specific scene)
    RenderPipeline* get_scene_pipeline(tc_scene_handle scene, const std::string& name) const;

    // Get scene pipeline by name (searches all scenes)
    RenderPipeline* get_scene_pipeline(const std::string& name) const;

    // Pipeline targets (viewport names for each pipeline)
    void set_pipeline_targets(const std::string& pipeline_name, const std::vector<std::string>& targets);
    const std::vector<std::string>& get_pipeline_targets(const std::string& pipeline_name) const;

    // Get all pipeline names for a scene
    std::vector<std::string> get_pipeline_names(tc_scene_handle scene) const;

    // Clear all pipelines for a scene (called at render detach time)
    // Calls tc_scene_notify_render_detach before destroying pipelines.
    void clear_scene_pipelines(tc_scene_handle scene);

    // Clear all scene pipelines
    void clear_all_scene_pipelines();

    // ========================================================================
    // Shutdown
    // ========================================================================

    // Cleanup all resources
    void shutdown();

    // ========================================================================
    // Low-level Presentation (for RenderingController)
    // ========================================================================

    // Blit viewports to single display
    void present_display(tc_display* display);

private:
    // Render single viewport to its output FBO
    void render_viewport_offscreen(tc_viewport_handle viewport);

    // Render scene pipeline to viewport output FBOs
    void render_scene_pipeline_offscreen(
        tc_scene_handle scene,
        const std::string& pipeline_name,
        RenderPipeline* pipeline
    );

    // Collect lights from scene (simplified - returns empty for now)
    std::vector<Light> collect_lights(tc_scene_handle scene);

    // Apply scene pipelines after viewports are created
    void apply_scene_pipelines(tc_scene_handle scene, const std::vector<tc_viewport_handle>& viewports);

    // Collect all viewports from all displays by name
    std::unordered_map<std::string, tc_viewport_handle> collect_all_viewports() const;

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

    // Callback to activate GL context before rendering
    MakeCurrentCallback make_current_callback_;

    // GPU context for offscreen rendering (push model)
    tc_gpu_context* offscreen_gpu_context_ = nullptr;

    // Factory for creating displays on demand
    DisplayFactory display_factory_;

    // Factory for creating pipelines by special name
    PipelineFactory pipeline_factory_;

    // Attached scenes (for scene pipeline execution)
    std::vector<tc_scene_handle> attached_scenes_;

    // Scene pipelines: scene_handle -> (pipeline_name -> owning pointer)
    // RenderingManager owns compiled pipelines
    // Key is (scene.index << 32 | scene.generation)
    std::unordered_map<uint64_t, std::unordered_map<std::string, std::unique_ptr<RenderPipeline>>> scene_pipelines_;

    // Pipeline targets: pipeline_name -> list of viewport names
    std::unordered_map<std::string, std::vector<std::string>> pipeline_targets_;

    // Helper to make key from scene handle
    static uint64_t scene_key(tc_scene_handle h) {
        return (static_cast<uint64_t>(h.index) << 32) | h.generation;
    }
};

} // namespace termin
