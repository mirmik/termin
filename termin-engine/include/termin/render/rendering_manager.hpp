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

#include "termin/engine/termin_engine_api.hpp"
#include "termin/render/viewport_render_state.hpp"
#include "termin/render/render_pipeline.hpp"
#include "termin/render/render_engine.hpp"

extern "C" {
#include "core/tc_scene.h"
#include "tc_viewport_config.h"
#include "render/tc_display.h"
#include "render/tc_viewport.h"
#include "render/tc_viewport_pool.h"
#include "render/tc_render_target.h"
#include "render/tc_render_surface.h"
}

#include <vector>
#include <unordered_map>
#include <unordered_set>
#include <memory>
#include <functional>
#include <string>

namespace termin {

class RenderingManager;

namespace rendering_manager_detail {
class RenderDisplayRegistry;
class RenderStateStore;
class ScenePipelineManager;
}

// Factory callback types
using DisplayFactory = std::function<tc_display*(const std::string& name)>;
using PipelineFactory = std::function<tc_pipeline_handle(const std::string& name)>;
using MakeCurrentCallback = std::function<void()>;
using DisplayRemovedCallback = std::function<void(tc_display*)>;
using RenderRequestCallback = std::function<void()>;
using RenderTargetContextProvider = std::function<bool(
    RenderingManager& manager,
    tc_render_target_handle render_target,
    const std::string& base_context_name,
    tc_entity_handle internal_entities,
    std::unordered_map<std::string, RenderTargetContext>& contexts,
    std::string& default_context_name
)>;

// RenderingManager - manages displays and rendering
//
// Owned by EngineCore. Global instance() returns the one set by EngineCore.
// Thread safety: NOT thread-safe. All calls must be from main/render thread.
class TERMIN_ENGINE_API RenderingManager {
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

    // Set render engine (optional, created lazily if not set)
    void set_render_engine(RenderEngine* engine);
    RenderEngine* render_engine();

    // Set callback to activate GL context before rendering
    void set_make_current_callback(MakeCurrentCallback callback);

    // Set factory for creating displays on demand
    void set_display_factory(DisplayFactory factory);

    // Set factory for creating pipelines by special name (e.g., "(Editor)")
    void set_pipeline_factory(PipelineFactory factory);

    // Set callback used when rendering state changes outside the editor UI
    // event path and a pull-mode host must render another frame.
    void set_render_request_callback(RenderRequestCallback callback);
    void request_render_update();

    // Register a provider for special render target kinds. Texture targets
    // are built internally; XR stereo targets use this hook to supply per-eye
    // RenderTargetContext objects for the current runtime frame.
    void set_render_target_context_provider(
        tc_render_target_kind kind,
        RenderTargetContextProvider provider
    );
    void clear_render_target_context_provider(tc_render_target_kind kind);

    // Create pipeline by name (uses C++ factory for "(Default)"/"Default", Python factory for rest)
    tc_pipeline_handle create_pipeline(const std::string& name);

    // Recreate live render-target pipelines that were created from the given
    // pipeline asset. Returns the number of render targets rebound.
    size_t recreate_render_target_pipelines_for_asset(
        const std::string& asset_name,
        const std::string& asset_uuid
    );

    // Recompile scene pipelines mounted from the given scene-pipeline asset.
    // Returns the number of attached scenes that were rebuilt.
    size_t recreate_scene_pipelines_for_asset(
        const std::string& asset_name,
        const std::string& asset_uuid
    );

    // Create default render pipeline (Shadow, Skybox, Color, Transparent, Resolve, PostFX, UIWidgets, Present)
    static tc_pipeline_handle make_default_pipeline();

    // Set callback called when a display is removed (for cleanup in editor)
    void set_display_removed_callback(DisplayRemovedCallback callback);

    // ========================================================================
    // Display Management
    // ========================================================================

    // Add display to management (scene display, cleaned up by detach_scene_full)
    void add_display(tc_display* display);

    // Remove display from management
    void remove_display(tc_display* display);

    // Get all managed scene displays
    const std::vector<tc_display*>& displays() const;

    // Add editor display (skipped by detach_scene_full/unmount_scene)
    void add_editor_display(tc_display* display);

    // Remove editor display
    void remove_editor_display(tc_display* display);

    // Get all editor displays
    const std::vector<tc_display*>& editor_displays() const;

    // Find display by name (searches both scene and editor displays)
    tc_display* get_display_by_name(const std::string& name) const;

    // Get existing display or create via factory
    tc_display* get_or_create_display(const std::string& name);

    // Check if display should be auto-removed (empty + auto_remove_when_empty flag)
    // Returns true if display was removed.
    bool try_auto_remove_display(tc_display* display);

    // Ensure display has a DisplayInputRouter (creates one if missing).
    // Returns the router's tc_input_manager pointer.
    tc_input_manager* ensure_display_router(tc_display* display);

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
    // Render Target State
    // ========================================================================

    // Get render state for a render target (returns nullptr if not found)
    ViewportRenderState* get_render_target_state(tc_render_target_handle rt);

    // Get or create render state for a render target
    ViewportRenderState* get_or_create_render_target_state(tc_render_target_handle rt);

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
        tc_component* camera,
        float region_x, float region_y, float region_w, float region_h,
        tc_pipeline_handle pipeline,
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
    tc_pipeline_handle get_scene_pipeline(tc_scene_handle scene, const std::string& name) const;

    // Get scene pipeline by name (searches all scenes)
    tc_pipeline_handle get_scene_pipeline(const std::string& name) const;

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
    // Managed Render Target Management
    // ========================================================================

    // Register a render target managed by RenderingManager.
    // The manager will track it for rendering and scene-detach cleanup.
    void register_managed_render_target(tc_render_target_handle rt);

    // Unregister a render target managed by RenderingManager.
    void unregister_managed_render_target(tc_render_target_handle rt);

    // Get all render targets managed by RenderingManager.
    const std::vector<tc_render_target_handle>& managed_render_targets() const {
        return managed_render_targets_;
    }

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

public:
    // Render a single managed render target to its output FBO
    void render_render_target_offscreen(tc_render_target_handle rt);

private:

    // Sync dynamic-resolution render targets: update width/height from attached viewport pixel_rect
    void sync_viewport_resolutions();

    // Render scene pipeline to viewport output FBOs
    void render_scene_pipeline_offscreen(
        tc_scene_handle scene,
        const std::string& pipeline_name,
        tc_pipeline_handle pipeline
    );

    bool build_render_target_contexts(
        tc_render_target_handle rt,
        const std::string& base_context_name,
        tc_entity_handle internal_entities,
        int render_width,
        int render_height,
        std::unordered_map<std::string, RenderTargetContext>& contexts,
        std::string& default_context_name
    );

    // Collect lights from scene (simplified - returns empty for now)
    std::vector<Light> collect_lights(tc_scene_handle scene);

    // Apply scene pipelines after viewports are created
    void apply_scene_pipelines(tc_scene_handle scene, const std::vector<tc_viewport_handle>& viewports);

    // Collect all viewports from all displays by name
    std::unordered_map<std::string, tc_viewport_handle> collect_all_viewports() const;

private:
    // Scene/editor display lists and per-display input routers.
    std::unique_ptr<rendering_manager_detail::RenderDisplayRegistry> display_registry_;

    // Render engine (owned if created internally)
    RenderEngine* render_engine_ = nullptr;
    std::unique_ptr<RenderEngine> owned_render_engine_;

    // Runtime GPU output state for viewports and render targets.
    std::unique_ptr<rendering_manager_detail::RenderStateStore> render_states_;

    // Compiled scene pipeline handles and target viewport mappings.
    std::unique_ptr<rendering_manager_detail::ScenePipelineManager> scene_pipelines_;

    // Callback to activate GL context before rendering
    MakeCurrentCallback make_current_callback_;

    // Last offscreen share-group key observed by the push model.
    uintptr_t offscreen_share_group_key_ = 0;

    // Factory for creating displays on demand
    DisplayFactory display_factory_;

    // Factory for creating pipelines by special name
    PipelineFactory pipeline_factory_;

    // Callback when a display is removed
    DisplayRemovedCallback display_removed_callback_;

    // Callback to request another frame in pull-rendering hosts.
    RenderRequestCallback render_request_callback_;

    // Attached scenes (for scene pipeline execution)
    std::vector<tc_scene_handle> attached_scenes_;

    // Render targets managed by this RenderingManager.
    // Used for offscreen rendering, viewport target lookup, and scene-detach cleanup.
    // RenderingManager code must use this list as the ownership boundary and
    // must not scan the global render-target pool for lookup or rebinding:
    // the pool may contain stale, foreign, or duplicate editor/game targets.
    std::vector<tc_render_target_handle> managed_render_targets_;

    // Special target providers, keyed by tc_render_target_kind.
    std::unordered_map<int, RenderTargetContextProvider> render_target_context_providers_;
    std::unordered_set<uint64_t> missing_render_target_provider_warnings_;
};

} // namespace termin
