// rendering_manager.cpp - Global rendering manager implementation
#include "termin/render/rendering_manager.hpp"
#include "termin/render/scene_pipeline_template.hpp"
#include "termin/render/render_camera.hpp"
#include <termin/entity/entity.hpp>
#include "termin/viewport/tc_viewport_handle.hpp"

extern "C" {
#include <tcbase/tc_log.h>
#include "core/tc_light_capability.h"
#include "core/tc_camera_capability.h"
#include <tgfx/tc_gpu.h>
#include "core/tc_scene.h"
#include "core/tc_scene_render_mount.h"
#include "core/tc_scene_pool.h"
#include "core/tc_entity_pool.h"
#include "core/tc_entity_pool_registry.h"
#include "tc_viewport_config.h"
#include "render/tc_viewport_pool.h"
#include "render/tc_rendering_manager.h"
#include "render/tc_pass.h"
#include "render/tc_pipeline.h"
#include "inspect/tc_inspect.h"
#include "inspect/tc_inspect_pass_adapter.h"
}

#include <algorithm>
#include <cstring>

namespace termin {

// Convert tc_camera_data to RenderCamera
static RenderCamera render_camera_from_cap(const tc_camera_data& cd) {
    RenderCamera rc;
    std::memcpy(rc.view.data, cd.view, sizeof(cd.view));
    std::memcpy(rc.projection.data, cd.projection, sizeof(cd.projection));
    rc.position = Vec3(cd.position[0], cd.position[1], cd.position[2]);
    rc.near_clip = cd.near_clip;
    rc.far_clip = cd.far_clip;
    return rc;
}

// Get RenderCamera from tc_component* via camera capability.
// Returns false if component has no camera capability.
static bool get_render_camera(tc_component* cam_comp, double aspect, RenderCamera* out) {
    const tc_camera_capability* cap = tc_camera_capability_get(cam_comp);
    if (!cap || !cap->vtable || !cap->vtable->get_camera_data) return false;
    tc_camera_data cd;
    if (!cap->vtable->get_camera_data(cam_comp, aspect, &cd)) return false;
    *out = render_camera_from_cap(cd);
    return true;
}

// Helper to make a unique key from viewport handle
static inline uint64_t viewport_key(tc_viewport_handle h) {
    return (static_cast<uint64_t>(h.index) << 32) | h.generation;
}

// ============================================================================
// Global instance - set by EngineCore, accessed via C API for cross-DLL safety
// ============================================================================

RenderingManager* RenderingManager::s_instance = nullptr;

RenderingManager& RenderingManager::instance() {
    // Check global storage (cross-DLL safe)
    RenderingManager* global = reinterpret_cast<RenderingManager*>(tc_rendering_manager_instance());
    if (global) {
        s_instance = global;
        return *global;
    }

    // Fallback to local static (legacy, will be removed)
    if (s_instance) {
        return *s_instance;
    }

    tc_log(TC_LOG_ERROR, "[RenderingManager] instance() called but no instance set. Create EngineCore first.");
    static RenderingManager fallback;
    return fallback;
}

void RenderingManager::set_instance(RenderingManager* instance) {
    s_instance = instance;
    tc_rendering_manager_set_instance(reinterpret_cast<tc_rendering_manager*>(instance));
}

void RenderingManager::reset_for_testing() {
    s_instance = nullptr;
    tc_rendering_manager_set_instance(nullptr);
}

RenderingManager::RenderingManager() {
    set_instance(this);
}

RenderingManager::~RenderingManager() {
    shutdown();
    if (s_instance == this) {
        set_instance(nullptr);
    }
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

void RenderingManager::set_make_current_callback(MakeCurrentCallback callback) {
    make_current_callback_ = std::move(callback);
}

void RenderingManager::set_display_factory(DisplayFactory factory) {
    display_factory_ = std::move(factory);
}

void RenderingManager::set_pipeline_factory(PipelineFactory factory) {
    pipeline_factory_ = std::move(factory);
}

tc_pipeline_handle RenderingManager::create_pipeline(const std::string& name) {
    if (name == "(Default)" || name == "Default" || name.empty()) {
        return make_default_pipeline();
    }
    if (pipeline_factory_) {
        return pipeline_factory_(name);
    }
    return TC_PIPELINE_HANDLE_INVALID;
}

// Helper: create pass by type name, set pass_name and string fields via inspect
static tc_pass* create_and_configure_pass(
    const char* type_name,
    const char* pass_name,
    std::initializer_list<std::pair<const char*, const char*>> fields
) {
    tc_pass* pass = tc_pass_registry_create(type_name);
    if (!pass) {
        tc_log(TC_LOG_WARN, "[make_default_pipeline] Failed to create pass '%s'", type_name);
        return nullptr;
    }
    tc_pass_set_name(pass, pass_name);
    for (auto& [field, value] : fields) {
        tc_value v = tc_value_string(value);
        tc_pass_inspect_set(pass, field, v, nullptr);
        tc_value_free(&v);
    }
    return pass;
}

tc_pipeline_handle RenderingManager::make_default_pipeline() {
    tc_pipeline_handle ph = tc_pipeline_create("Default");

    // 1. ShadowPass
    if (tc_pass* p = create_and_configure_pass("ShadowPass", "Shadow", {
            {"output_res", "shadow_maps"}
        })) {
        tc_pipeline_add_pass(ph, p);
    }

    // 2. SkyBoxPass
    if (tc_pass* p = create_and_configure_pass("SkyBoxPass", "Skybox", {
            {"input_res", "empty"},
            {"output_res", "skybox"}
        })) {
        tc_pipeline_add_pass(ph, p);
    }

    // 3. ColorPass (opaque)
    if (tc_pass* p = create_and_configure_pass("ColorPass", "Color", {
            {"input_res", "skybox"},
            {"output_res", "color_opaque"},
            {"shadow_res", "shadow_maps"},
            {"phase_mark", "opaque"}
        })) {
        tc_pipeline_add_pass(ph, p);
    }

    // 4. ColorPass (transparent)
    if (tc_pass* p = create_and_configure_pass("ColorPass", "Transparent", {
            {"input_res", "color_opaque"},
            {"output_res", "color"},
            {"shadow_res", ""},
            {"phase_mark", "transparent"},
            {"sort_mode", "far_to_near"}
        })) {
        tc_pipeline_add_pass(ph, p);
    }

    if (tc_pass* p = create_and_configure_pass("BloomPass", "Bloom", {
        {"input_res", "color"},
        {"output_res", "color_bloom"},
    })) {
        tc_pipeline_add_pass(ph, p);
    }

    // 5. UIWidgetPass
    if (tc_pass* p = create_and_configure_pass("UIWidgetPass", "UIWidgets", {
            {"input_res", "color_bloom"},
            {"output_res", "color+widgets"}
        })) {
        tc_pipeline_add_pass(ph, p);
    }

    // 7. PresentToScreenPass
    if (tc_pass* p = create_and_configure_pass("PresentToScreenPass", "Present", {
            {"input_res", "color+widgets"}
        })) {
        tc_pipeline_add_pass(ph, p);
    }

    return ph;
}

void RenderingManager::set_display_removed_callback(DisplayRemovedCallback callback) {
    display_removed_callback_ = std::move(callback);
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

    // Remove display router if exists
    display_routers_.erase(display);

    displays_.erase(it);

    // Notify callback (e.g., editor cleanup of Qt tabs)
    if (display_removed_callback_) {
        display_removed_callback_(display);
    }
}

bool RenderingManager::try_auto_remove_display(tc_display* display) {
    if (!display) return false;
    if (!tc_display_get_auto_remove_when_empty(display)) return false;
    if (tc_display_get_viewport_count(display) > 0) return false;

    remove_display(display);
    return true;
}

tc_input_manager* RenderingManager::ensure_display_router(tc_display* display) {
    if (!display) return nullptr;

    auto it = display_routers_.find(display);
    if (it != display_routers_.end()) {
        return it->second->input_manager_ptr();
    }

    auto router = std::make_unique<DisplayInputRouter>(display);
    tc_input_manager* im = router->input_manager_ptr();
    display_routers_[display] = std::move(router);
    return im;
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

tc_display* RenderingManager::get_or_create_display(const std::string& name) {
    // Check existing displays
    tc_display* display = get_display_by_name(name);
    if (display) {
        return display;
    }

    // Try factory
    if (display_factory_) {
        display = display_factory_(name);
        if (display) {
            add_display(display);
            return display;
        }
    }

    return nullptr;
}

// ============================================================================
// Scene Mounting
// ============================================================================

tc_viewport_handle RenderingManager::mount_scene(
    tc_scene_handle scene,
    tc_display* display,
    tc_component* camera,
    float region_x, float region_y, float region_w, float region_h,
    tc_pipeline_handle pipeline,
    const std::string& name
) {
    if (!tc_scene_handle_valid(scene) || !display || !camera) {
        return TC_VIEWPORT_HANDLE_INVALID;
    }

    // Create viewport (render target must be assigned by caller)
    tc_viewport_handle viewport = tc_viewport_pool_alloc(name.c_str());
    if (!tc_viewport_handle_valid(viewport)) {
        tc_log(TC_LOG_ERROR, "[RenderingManager] Failed to create viewport '%s'", name.c_str());
        return TC_VIEWPORT_HANDLE_INVALID;
    }

    // Set rect
    tc_viewport_set_rect(viewport, region_x, region_y, region_w, region_h);

    // Add to display
    tc_display_add_viewport(display, viewport);

    return viewport;
}

void RenderingManager::unmount_scene(tc_scene_handle scene, tc_display* display) {
    if (!display) return;

    // Collect viewports showing this scene
    std::vector<tc_viewport_handle> to_remove;
    tc_viewport_handle vp = tc_display_get_first_viewport(display);
    while (tc_viewport_handle_valid(vp)) {
        tc_scene_handle vp_scene = tc_viewport_get_scene(vp);
        if (tc_scene_handle_eq(vp_scene, scene)) {
            to_remove.push_back(vp);
        }
        vp = tc_viewport_get_display_next(vp);
    }

    // Remove them
    for (tc_viewport_handle viewport : to_remove) {
        // Remove viewport state
        remove_viewport_state(viewport);

        // Remove from display
        tc_display_remove_viewport(display, viewport);

        // Free viewport
        tc_viewport_free(viewport);
    }
}

// Helper struct for camera search callback
// Find first component with camera capability in scene
struct CameraSearchData {
    tc_component* camera;
    const char* found_name;
};

static bool find_first_camera_cb(tc_component* c, void* user_data) {
    CameraSearchData* data = static_cast<CameraSearchData*>(user_data);
    data->camera = c;
    if (tc_entity_handle_valid(c->owner)) {
        tc_entity_pool* pool = tc_entity_pool_registry_get(c->owner.pool);
        if (pool) data->found_name = tc_entity_pool_name(pool, c->owner.id);
    }
    return false; // Stop iteration — found first camera
}

std::vector<tc_viewport_handle> RenderingManager::attach_scene_full(tc_scene_handle scene) {
    std::vector<tc_viewport_handle> viewports;

    if (!tc_scene_handle_valid(scene)) {
        tc_log(TC_LOG_ERROR, "[RenderingManager] attach_scene_full: invalid scene handle");
        return viewports;
    }

    tc_scene_render_mount* mount = tc_scene_render_mount_get(scene);
    tc_entity_pool* pool = tc_scene_entity_pool(scene);
    tc_entity_pool_handle pool_handle = pool ? tc_entity_pool_registry_find(pool) : TC_ENTITY_POOL_HANDLE_INVALID;

    // 1. Create render targets from render_target_configs
    std::unordered_map<std::string, tc_render_target_handle> rt_by_name;
    size_t rt_count = mount ? mount->render_target_config_count : 0;
    for (size_t i = 0; i < rt_count; i++) {
        tc_render_target_config* rtc = &mount->render_target_configs[i];
        std::string rt_name = rtc->name ? rtc->name : "";
        if (rt_name.empty()) continue;

        tc_render_target_handle rt = tc_render_target_new(rt_name.c_str());
        tc_render_target_set_scene(rt, scene);
        tc_render_target_set_width(rt, rtc->width);
        tc_render_target_set_height(rt, rtc->height);
        tc_render_target_set_layer_mask(rt, rtc->layer_mask);
        tc_render_target_set_enabled(rt, rtc->enabled);

        // Find camera by UUID
        if (rtc->camera_uuid && rtc->camera_uuid[0] != '\0' && pool) {
            tc_entity_id eid = tc_entity_pool_find_by_uuid(pool, rtc->camera_uuid);
            if (tc_entity_id_valid(eid)) {
                tc_entity_handle eh = tc_entity_handle_make(pool_handle, eid);
                Entity entity(eh);
                tc_component* camera = entity.get_component_by_type_name("CameraComponent");
                if (camera) {
                    tc_render_target_set_camera(rt, camera);
                }
            }
        }

        // Get pipeline
        tc_pipeline_handle pipeline = TC_PIPELINE_HANDLE_INVALID;
        if (rtc->pipeline_uuid && rtc->pipeline_uuid[0] != '\0' && pipeline_factory_) {
            pipeline = pipeline_factory_(rtc->pipeline_uuid);
        }
        if (!tc_pipeline_handle_valid(pipeline) && rtc->pipeline_name && rtc->pipeline_name[0] != '\0' && pipeline_factory_) {
            pipeline = pipeline_factory_(rtc->pipeline_name);
        }
        if (tc_pipeline_handle_valid(pipeline)) {
            tc_render_target_set_pipeline(rt, pipeline);
        }

        rt_by_name[rt_name] = rt;
    }

    // 2. Create viewports from viewport_configs, link to render targets by name
    size_t vp_count = mount ? mount->viewport_config_count : 0;
    for (size_t i = 0; i < vp_count; i++) {
        tc_viewport_config* config = &mount->viewport_configs[i];

        std::string display_name = config->display_name ? config->display_name : "Main";
        tc_display* display = get_or_create_display(display_name);
        if (!display) {
            tc_log(TC_LOG_WARN, "[RenderingManager] Cannot create display '%s'", display_name.c_str());
            continue;
        }

        std::string vp_name = config->name ? config->name : "";
        tc_viewport_handle viewport = tc_viewport_pool_alloc(vp_name.c_str());
        if (!tc_viewport_handle_valid(viewport)) continue;

        tc_viewport_set_rect(viewport, config->region[0], config->region[1], config->region[2], config->region[3]);
        tc_viewport_set_depth(viewport, config->depth);
        tc_viewport_set_enabled(viewport, config->enabled);
        if (config->input_mode) {
            tc_viewport_set_input_mode(viewport, config->input_mode);
        }
        tc_viewport_set_block_input_in_editor(viewport, config->block_input_in_editor);

        // Link to render target by name
        std::string rt_name = config->render_target_name ? config->render_target_name : "";
        if (!rt_name.empty()) {
            auto it = rt_by_name.find(rt_name);
            if (it != rt_by_name.end()) {
                tc_viewport_set_render_target(viewport, it->second);
            } else {
                tc_log(TC_LOG_WARN, "[RenderingManager] Render target '%s' not found for viewport '%s'",
                       rt_name.c_str(), vp_name.c_str());
            }
        }

        tc_display_add_viewport(display, viewport);
        viewports.push_back(viewport);
    }

    // Apply scene pipelines (compile templates, mark managed viewports)
    apply_scene_pipelines(scene, viewports);

    // Track attached scene
    auto it = std::find_if(attached_scenes_.begin(), attached_scenes_.end(),
        [scene](tc_scene_handle h) { return tc_scene_handle_eq(h, scene); });
    if (it == attached_scenes_.end()) {
        attached_scenes_.push_back(scene);
    }

    return viewports;
}

void RenderingManager::detach_scene_full(tc_scene_handle scene) {
    // Unmount from all displays
    for (tc_display* display : displays_) {
        unmount_scene(scene, display);
    }

    // Free render targets belonging to this scene (not locked)
    struct FreeCtx { tc_scene_handle scene; RenderingManager* mgr; std::vector<tc_render_target_handle> to_free; };
    FreeCtx free_ctx = { scene, this, {} };
    tc_render_target_pool_foreach([](tc_render_target_handle rt, void* ud) -> bool {
        auto* ctx = static_cast<FreeCtx*>(ud);
        tc_scene_handle rt_scene = tc_render_target_get_scene(rt);
        if (tc_scene_handle_eq(rt_scene, ctx->scene) && !tc_render_target_get_locked(rt)) {
            ctx->to_free.push_back(rt);
        }
        return true;
    }, &free_ctx);
    for (tc_render_target_handle rt : free_ctx.to_free) {
        uint64_t rt_key = render_target_key(rt);
        auto rt_it = render_target_states_.find(rt_key);
        if (rt_it != render_target_states_.end()) {
            rt_it->second->clear_all();
            render_target_states_.erase(rt_it);
        }
        tc_render_target_free(rt);
    }

    // Remove from attached scenes
    auto it = std::find_if(attached_scenes_.begin(), attached_scenes_.end(),
        [scene](tc_scene_handle h) { return tc_scene_handle_eq(h, scene); });
    if (it != attached_scenes_.end()) {
        attached_scenes_.erase(it);
    }

    // Detach scene pipelines
    detach_scene(scene);
}

void RenderingManager::apply_scene_pipelines(tc_scene_handle scene, const std::vector<tc_viewport_handle>& viewports) {
    // Compile scene pipeline templates (this calls attach_scene internally)
    attach_scene(scene);

    // Build viewport lookup by name
    std::unordered_map<std::string, tc_viewport_handle> viewport_by_name;
    for (tc_viewport_handle vp : viewports) {
        const char* name = tc_viewport_get_name(vp);
        if (name && name[0] != '\0') {
            viewport_by_name[name] = vp;
        }
    }

    // Also check all displays for viewports
    for (tc_display* display : displays_) {
        tc_viewport_handle vp = tc_display_get_first_viewport(display);
        while (tc_viewport_handle_valid(vp)) {
            const char* name = tc_viewport_get_name(vp);
            if (name && name[0] != '\0') {
                if (viewport_by_name.find(name) == viewport_by_name.end()) {
                    viewport_by_name[name] = vp;
                }
            }
            vp = tc_viewport_get_display_next(vp);
        }
    }

    // Mark viewports as managed by their scene pipeline
    tc_scene_render_mount* mount = tc_scene_render_mount_get(scene);
    size_t template_count = mount ? mount->pipeline_template_count : 0;
    for (size_t i = 0; i < template_count; i++) {
        tc_spt_handle spt_handle = mount->pipeline_templates[i];
        if (!tc_spt_is_valid(spt_handle)) continue;

        TcScenePipelineTemplate templ(spt_handle);
        if (!templ.is_loaded()) continue;

        std::string pipeline_name = templ.name();
        std::vector<std::string> targets = templ.target_viewports();

        for (const std::string& vp_name : targets) {
            auto it = viewport_by_name.find(vp_name);
            if (it == viewport_by_name.end()) {
                tc_log(TC_LOG_ERROR, "[RenderingManager] Scene pipeline '%s' targets viewport '%s' but not found",
                       pipeline_name.c_str(), vp_name.c_str());
                continue;
            }
            tc_viewport_set_managed_by(it->second, pipeline_name.c_str());
        }
    }
}

std::unordered_map<std::string, tc_viewport_handle> RenderingManager::collect_all_viewports() const {
    std::unordered_map<std::string, tc_viewport_handle> result;
    for (tc_display* display : displays_) {
        tc_viewport_handle vp = tc_display_get_first_viewport(display);
        while (tc_viewport_handle_valid(vp)) {
            const char* name = tc_viewport_get_name(vp);
            if (name && name[0] != '\0') {
                result[name] = vp;
            }
            vp = tc_viewport_get_display_next(vp);
        }
    }
    return result;
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
        // Ensure GL context is current before deleting GPU resources
        if (make_current_callback_) {
            make_current_callback_();
        }
        if (offscreen_gpu_context_) {
            tc_gpu_set_context(offscreen_gpu_context_);
        }
        it->second->clear_all();
        viewport_states_.erase(it);
    }
}

// ============================================================================
// Render Target State
// ============================================================================

ViewportRenderState* RenderingManager::get_render_target_state(tc_render_target_handle rt) {
    uint64_t key = render_target_key(rt);
    auto it = render_target_states_.find(key);
    return it != render_target_states_.end() ? it->second.get() : nullptr;
}

ViewportRenderState* RenderingManager::get_or_create_render_target_state(tc_render_target_handle rt) {
    uint64_t key = render_target_key(rt);
    auto it = render_target_states_.find(key);
    if (it != render_target_states_.end()) return it->second.get();
    auto& state = render_target_states_[key];
    state = std::make_unique<ViewportRenderState>();
    return state.get();
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

    // Activate GL context via callback
    if (make_current_callback_) {
        make_current_callback_();
    }

    // Set offscreen GPU context (lazy-create)
    if (!offscreen_gpu_context_) {
        offscreen_gpu_context_ = tc_gpu_context_new(0, NULL);
        tc_gpu_context_set_name(offscreen_gpu_context_, "offscreen");
    }
    tc_gpu_set_context(offscreen_gpu_context_);

    RenderEngine* engine = render_engine();
    if (!engine) {
        tc_log(TC_LOG_WARN, "[RenderingManager] render_all_offscreen: no render engine");
        return;
    }

    // 0. Sync viewport override_resolution → render target width/height
    sync_viewport_resolutions();

    // 1. Execute scene pipelines (can span multiple displays)
    for (tc_scene_handle scene : attached_scenes_) {
        if (!tc_scene_handle_valid(scene)) continue;

        std::vector<std::string> pipeline_names = get_pipeline_names(scene);
        for (const std::string& pipeline_name : pipeline_names) {
            tc_pipeline_handle pipeline = get_scene_pipeline(scene, pipeline_name);
            if (tc_pipeline_handle_valid(pipeline)) {
                render_scene_pipeline_offscreen(scene, pipeline_name, pipeline);
            }
        }
    }

    // 2. Render unmanaged viewports
    for (tc_display* display : displays_) {
        if (!tc_display_get_enabled(display)) continue;

        tc_viewport_handle vp = tc_display_get_first_viewport(display);
        while (tc_viewport_handle_valid(vp)) {
            if (tc_viewport_get_enabled(vp)) {
                const char* managed_by = tc_viewport_get_managed_by(vp);
                // Skip viewports managed by scene pipeline
                if (!managed_by || managed_by[0] == '\0') {
                    render_viewport_offscreen(vp);
                }
            }
            vp = tc_viewport_get_display_next(vp);
        }
    }

    // 3. Render all render targets from pool
    struct RenderTargetIterCtx { RenderingManager* mgr; };
    RenderTargetIterCtx rt_ctx = { this };
    tc_render_target_pool_foreach([](tc_render_target_handle rt, void* ud) -> bool {
        auto* ctx = static_cast<RenderTargetIterCtx*>(ud);
        ctx->mgr->render_render_target_offscreen(rt);
        return true;
    }, &rt_ctx);
}

void RenderingManager::render_scene_pipeline_offscreen(
    tc_scene_handle scene,
    const std::string& pipeline_name,
    tc_pipeline_handle pipeline
) {
    if (!tc_scene_handle_valid(scene) || !tc_pipeline_handle_valid(pipeline) || !graphics_) {
        return;
    }

    const std::vector<std::string>& target_names = get_pipeline_targets(pipeline_name);
    if (target_names.empty()) {
        return;
    }

    auto all_viewports = collect_all_viewports();

    // Collect viewport contexts
    std::unordered_map<std::string, ViewportContext> contexts;
    std::string first_viewport_name;

    for (const std::string& vp_name : target_names) {
        auto it = all_viewports.find(vp_name);
        if (it == all_viewports.end()) {
            tc_log(TC_LOG_ERROR, "[RenderingManager] Scene pipeline '%s' target viewport '%s' NOT FOUND",
                   pipeline_name.c_str(), vp_name.c_str());
            continue;
        }

        tc_viewport_handle viewport = it->second;
        if (!tc_viewport_get_enabled(viewport)) {
            tc_log(TC_LOG_WARN, "[RenderingManager] Viewport '%s' is disabled, skipping", vp_name.c_str());
            continue;
        }

        tc_component* camera_comp = tc_viewport_get_camera(viewport);
        if (!camera_comp) {
            tc_log(TC_LOG_WARN, "[RenderingManager] Viewport '%s' has no camera", vp_name.c_str());
            continue;
        }

        if (first_viewport_name.empty()) {
            first_viewport_name = vp_name;
        }

        // Get pixel rect
        int px, py, pw, ph;
        tc_viewport_get_pixel_rect(viewport, &px, &py, &pw, &ph);
        if (pw <= 0 || ph <= 0) {
            tc_log(TC_LOG_WARN, "[RenderingManager] Viewport '%s' has invalid pixel_rect: %dx%d",
                   vp_name.c_str(), pw, ph);
            continue;
        }

        double aspect = static_cast<double>(pw) / std::max(1, ph);
        RenderCamera render_cam;
        if (!get_render_camera(camera_comp, aspect, &render_cam)) {
            tc_log(TC_LOG_WARN, "[RenderingManager] Viewport '%s' camera has no camera capability", vp_name.c_str());
            continue;
        }

        // Ensure output FBO (stored on render target state)
        tc_render_target_handle rt = tc_viewport_get_render_target(viewport);
        ViewportRenderState* state = nullptr;
        if (tc_render_target_handle_valid(rt)) {
            state = get_or_create_render_target_state(rt);
        } else {
            state = get_or_create_viewport_state(viewport);
        }
        FramebufferHandle* output_fbo = state->ensure_output_fbo(graphics_, pw, ph);

        // Create viewport context
        ViewportContext ctx;
        ctx.name = vp_name;
        ctx.camera = render_cam;
        ctx.rect = {0, 0, pw, ph};  // Full FBO, offset at blit time
        ctx.internal_entities = tc_viewport_get_internal_entities(viewport);
        ctx.layer_mask = tc_viewport_get_layer_mask(viewport);
        ctx.output_fbo = output_fbo;
        contexts[vp_name] = std::move(ctx);
    }

    if (contexts.empty()) {
        return;
    }

    // Collect lights
    std::vector<Light> lights = collect_lights(scene);

    // Execute pipeline for all contexts
    RenderEngine* engine = render_engine();
    RenderPipeline pipeline_wrapper(pipeline);
    engine->render_scene_pipeline_offscreen(
        pipeline_wrapper,
        scene,
        contexts,
        lights,
        first_viewport_name
    );
}

void RenderingManager::render_viewport_offscreen(tc_viewport_handle viewport) {
    const char* vp_name = tc_viewport_get_name(viewport);

    if (!tc_viewport_handle_valid(viewport) || !graphics_) {
        tc_log(TC_LOG_WARN, "[RenderingManager] render_viewport_offscreen('%s'): invalid viewport or no graphics",
               vp_name ? vp_name : "(null)");
        return;
    }

    tc_render_target_handle rt = tc_viewport_get_render_target(viewport);
    if (!tc_render_target_handle_valid(rt)) {
        return;
    }

    tc_scene_handle scene = tc_viewport_get_scene(viewport);
    tc_component* camera_comp = tc_viewport_get_camera(viewport);
    tc_pipeline_handle pipeline = tc_viewport_get_pipeline(viewport);

    if (!tc_scene_handle_valid(scene)) {
        return;
    }
    if (!camera_comp) {
        tc_log(TC_LOG_WARN, "[RenderingManager] render_viewport_offscreen('%s'): no camera",
               vp_name ? vp_name : "(null)");
        return;
    }
    if (!tc_pipeline_handle_valid(pipeline)) {
        tc_log(TC_LOG_WARN, "[RenderingManager] render_viewport_offscreen('%s'): invalid pipeline handle",
               vp_name ? vp_name : "(null)");
        return;
    }

    // Wrap pipeline handle
    RenderPipeline render_pipeline(pipeline);

    // Get pixel rect
    int px, py, pw, ph;
    tc_viewport_get_pixel_rect(viewport, &px, &py, &pw, &ph);
    if (pw <= 0 || ph <= 0) return;

    double aspect = static_cast<double>(pw) / std::max(1, ph);
    RenderCamera render_camera;
    if (!get_render_camera(camera_comp, aspect, &render_camera)) {
        tc_log(TC_LOG_WARN, "[RenderingManager] render_viewport_offscreen('%s'): no camera capability",
               vp_name ? vp_name : "(null)");
        return;
    }

    // Ensure output FBO (stored on render target state)
    ViewportRenderState* state = get_or_create_render_target_state(rt);
    FramebufferHandle* output_fbo = state->ensure_output_fbo(graphics_, pw, ph);

    // Collect lights
    std::vector<Light> lights = collect_lights(scene);

    // Render to output FBO
    RenderEngine* engine = render_engine();
    tc_entity_handle internal_entities = tc_viewport_get_internal_entities(viewport);
    engine->render_view_to_fbo(
        render_pipeline,
        output_fbo,
        pw, ph,
        scene,
        render_camera,
        vp_name ? vp_name : "",
        internal_entities,
        lights,
        tc_viewport_get_layer_mask(viewport)
    );
}

void RenderingManager::sync_viewport_resolutions() {
    for (tc_display* display : displays_) {
        if (!tc_display_get_enabled(display)) continue;

        tc_viewport_handle vp = tc_display_get_first_viewport(display);
        while (tc_viewport_handle_valid(vp)) {
            if (tc_viewport_get_override_resolution(vp)) {
                tc_render_target_handle rt = tc_viewport_get_render_target(vp);
                if (tc_render_target_handle_valid(rt)) {
                    int px, py, pw, ph;
                    tc_viewport_get_pixel_rect(vp, &px, &py, &pw, &ph);
                    if (pw > 0 && ph > 0) {
                        tc_render_target_set_width(rt, pw);
                        tc_render_target_set_height(rt, ph);
                    }
                }
            }
            vp = tc_viewport_get_display_next(vp);
        }
    }
}

void RenderingManager::render_render_target_offscreen(tc_render_target_handle rt) {
    if (!tc_render_target_handle_valid(rt) || !graphics_) return;
    if (!tc_render_target_get_enabled(rt)) return;

    const char* rt_name = tc_render_target_get_name(rt);

    tc_scene_handle scene = tc_render_target_get_scene(rt);
    tc_component* camera_comp = tc_render_target_get_camera(rt);
    tc_pipeline_handle pipeline = tc_render_target_get_pipeline(rt);

    if (!tc_scene_handle_valid(scene)) {
        tc_log(TC_LOG_WARN, "[RenderingManager] RT '%s': no scene", rt_name ? rt_name : "?");
        return;
    }
    if (!camera_comp) {
        tc_log(TC_LOG_WARN, "[RenderingManager] RT '%s': no camera", rt_name ? rt_name : "?");
        return;
    }
    if (!tc_pipeline_handle_valid(pipeline)) {
        tc_log(TC_LOG_WARN, "[RenderingManager] RT '%s': no pipeline", rt_name ? rt_name : "?");
        return;
    }

    int w = tc_render_target_get_width(rt);
    int h = tc_render_target_get_height(rt);
    if (w <= 0 || h <= 0) {
        tc_log(TC_LOG_WARN, "[RenderingManager] RT '%s': invalid size %dx%d", rt_name ? rt_name : "?", w, h);
        return;
    }

    double aspect = static_cast<double>(w) / std::max(1, h);
    RenderCamera render_camera;
    if (!get_render_camera(camera_comp, aspect, &render_camera)) {
        tc_log(TC_LOG_WARN, "[RenderingManager] render_render_target_offscreen('%s'): no camera capability",
               rt_name ? rt_name : "(null)");
        return;
    }

    RenderPipeline render_pipeline(pipeline);

    ViewportRenderState* state = get_or_create_render_target_state(rt);
    FramebufferHandle* output_fbo = state->ensure_output_fbo(graphics_, w, h);

    std::vector<Light> lights = collect_lights(scene);

    RenderEngine* engine = render_engine();
    engine->render_view_to_fbo(
        render_pipeline,
        output_fbo,
        w, h,
        scene,
        render_camera,
        rt_name ? rt_name : "",
        TC_ENTITY_HANDLE_INVALID,
        lights,
        tc_render_target_get_layer_mask(rt)
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

    // Make display context current and set GPUContext
    tc_render_surface_make_current(surface);
    if (!surface->gpu_context) {
        {
            uintptr_t sg_key = tc_render_surface_share_group_key(surface);
            tc_gpu_share_group* group = tc_gpu_share_group_get_or_create(sg_key);
            surface->gpu_context = tc_gpu_context_new(tc_render_surface_context_key(surface), group);
            tc_gpu_share_group_unref(group);
        }
        const char* dname = tc_display_get_name(display);
        char ctx_name[32];
        snprintf(ctx_name, sizeof(ctx_name), "display:%s", dname ? dname : "?");
        tc_gpu_context_set_name(surface->gpu_context, ctx_name);
    }
    tc_gpu_set_context(surface->gpu_context);

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
        // Get render state from viewport's render target
        tc_render_target_handle rt = tc_viewport_get_render_target(viewport);
        ViewportRenderState* state = nullptr;
        if (tc_render_target_handle_valid(rt)) {
            state = get_render_target_state(rt);
        }
        // Fallback to viewport state (for legacy/transition)
        if (!state) {
            state = get_viewport_state(viewport);
        }
        if (!state || !state->has_output_fbo()) {
            continue;
        }

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

void RenderingManager::attach_scene(tc_scene_handle scene) {
    if (!tc_scene_handle_valid(scene)) return;

    // Clear existing pipelines (without notify_render_detach — attach will notify attach)
    clear_scene_pipelines(scene);

    tc_scene_render_mount* mount = tc_scene_render_mount_get(scene);
    size_t template_count = mount ? mount->pipeline_template_count : 0;
    uint64_t key = scene_key(scene);

    for (size_t i = 0; i < template_count; i++) {
        tc_spt_handle spt_handle = mount->pipeline_templates[i];
        if (!tc_spt_is_valid(spt_handle)) continue;

        TcScenePipelineTemplate templ(spt_handle);
        if (!templ.is_loaded()) {
            tc_log(TC_LOG_WARN, "[RenderingManager] Template not loaded: '%s'", templ.name().c_str());
            continue;
        }

        RenderPipeline* compiled = templ.compile();
        if (!compiled) {
            tc_log(TC_LOG_WARN, "[RenderingManager] Failed to compile template: '%s'", templ.name().c_str());
            continue;
        }

        std::string name = templ.name();
        tc_pipeline_handle ph = compiled->handle();
        tc_pipeline_set_name(ph, name.c_str());
        delete compiled; // RenderPipeline no longer owns — handle stays in pool

        // Store handle
        scene_pipelines_[key][name] = ph;

        // Store targets
        pipeline_targets_[name] = templ.target_viewports();
    }

    // Notify components that rendering is attached
    tc_scene_notify_render_attach(scene);
}

void RenderingManager::detach_scene(tc_scene_handle scene) {
    if (!tc_scene_handle_valid(scene)) return;
    tc_scene_notify_render_detach(scene);
    clear_scene_pipelines(scene);
}

tc_pipeline_handle RenderingManager::get_scene_pipeline(tc_scene_handle scene, const std::string& name) const {
    if (!tc_scene_handle_valid(scene)) return TC_PIPELINE_HANDLE_INVALID;
    uint64_t key = scene_key(scene);
    auto scene_it = scene_pipelines_.find(key);
    if (scene_it == scene_pipelines_.end()) return TC_PIPELINE_HANDLE_INVALID;
    auto pipe_it = scene_it->second.find(name);
    return (pipe_it != scene_it->second.end()) ? pipe_it->second : TC_PIPELINE_HANDLE_INVALID;
}

tc_pipeline_handle RenderingManager::get_scene_pipeline(const std::string& name) const {
    for (const auto& [key, pipelines] : scene_pipelines_) {
        auto it = pipelines.find(name);
        if (it != pipelines.end()) {
            return it->second;
        }
    }
    tc_log(TC_LOG_WARN, "[RenderingManager] get_scene_pipeline NOT FOUND: '%s'", name.c_str());
    return TC_PIPELINE_HANDLE_INVALID;
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
        for (const auto& [name, ptr] : scene_it->second) {
            (void)ptr;
            names.push_back(name);
        }
    }
    return names;
}

void RenderingManager::clear_scene_pipelines(tc_scene_handle scene) {
    if (!tc_scene_handle_valid(scene)) return;
    uint64_t key = scene_key(scene);

    auto scene_it = scene_pipelines_.find(key);
    if (scene_it == scene_pipelines_.end()) return;

    // Notify components that rendering is detaching (before destroying pipelines)
    tc_scene_notify_render_detach(scene);

    // Remove pipeline targets for this scene's pipelines
    for (const auto& [name, ptr] : scene_it->second) {
        (void)ptr;
        pipeline_targets_.erase(name);
    }

    // Destroy pipelines in pool, then erase
    for (const auto& [name, ph] : scene_it->second) {
        tc_pipeline_destroy(ph);
    }
    scene_pipelines_.erase(key);
}

void RenderingManager::clear_all_scene_pipelines() {
    // Notify all scenes that rendering is detaching
    for (const auto& [key, pipelines] : scene_pipelines_) {
        // Reconstruct scene handle from key
        tc_scene_handle scene;
        scene.index = static_cast<uint32_t>(key >> 32);
        scene.generation = static_cast<uint32_t>(key & 0xFFFFFFFF);
        if (tc_scene_handle_valid(scene)) {
            tc_scene_notify_render_detach(scene);
        }
    }

    // Destroy all pipelines, then clear
    for (auto& [key, pipelines] : scene_pipelines_) {
        for (auto& [name, ph] : pipelines) {
            tc_pipeline_destroy(ph);
        }
    }
    scene_pipelines_.clear();
    pipeline_targets_.clear();
}

// ============================================================================
// Shutdown
// ============================================================================

void RenderingManager::shutdown() {
    // Ensure GL context is current before deleting GPU resources
    if (make_current_callback_) {
        make_current_callback_();
    }
    if (offscreen_gpu_context_) {
        tc_gpu_set_context(offscreen_gpu_context_);
    }

    // Clear viewport states
    for (auto& pair : viewport_states_) {
        pair.second->clear_all();
    }
    viewport_states_.clear();

    // Clear attached scenes
    attached_scenes_.clear();

    // Clear scene pipelines (deletes owned pipelines)
    clear_all_scene_pipelines();

    // Clear display routers (before displays, since routers reference displays)
    display_routers_.clear();

    // Clear displays (don't free them - we don't own them)
    displays_.clear();

    // Free offscreen GPU context
    if (offscreen_gpu_context_) {
        tc_gpu_context_free(offscreen_gpu_context_);
        offscreen_gpu_context_ = nullptr;
    }

    // Clear callbacks
    make_current_callback_ = nullptr;
    display_factory_ = nullptr;
    pipeline_factory_ = nullptr;
    display_removed_callback_ = nullptr;

    // Release owned render engine
    owned_render_engine_.reset();
    render_engine_ = nullptr;

    graphics_ = nullptr;
}

// ============================================================================
// Helpers
// ============================================================================

// Light collection via capability system
static bool collect_lights_cap_cb(tc_component* c, void* user_data) {
    std::vector<Light>* lights = static_cast<std::vector<Light>*>(user_data);
    const tc_light_capability* cap = tc_light_capability_get(c);
    if (!cap || !cap->vtable || !cap->vtable->get_light_data) return true;

    tc_light_data ld;
    if (!cap->vtable->get_light_data(c, &ld)) return true;

    Light light;
    light.type = static_cast<LightType>(ld.type);
    light.color = Vec3(ld.color[0], ld.color[1], ld.color[2]);
    light.intensity = ld.intensity;
    light.direction = Vec3(ld.direction[0], ld.direction[1], ld.direction[2]);
    light.position = Vec3(ld.position[0], ld.position[1], ld.position[2]);
    if (ld.has_range) light.range = ld.range;
    light.inner_angle = ld.inner_angle;
    light.outer_angle = ld.outer_angle;
    light.shadows.enabled = ld.shadows.enabled;
    light.shadows.bias = ld.shadows.bias;
    light.shadows.normal_bias = ld.shadows.normal_bias;
    light.shadows.map_resolution = ld.shadows.map_resolution;
    light.shadows.cascade_count = ld.shadows.cascade_count;
    light.shadows.max_distance = ld.shadows.max_distance;
    light.shadows.split_lambda = ld.shadows.split_lambda;
    light.shadows.cascade_blend = ld.shadows.cascade_blend;
    light.shadows.blend_distance = ld.shadows.blend_distance;
    lights->push_back(std::move(light));
    return true;
}

std::vector<Light> RenderingManager::collect_lights(tc_scene_handle scene) {
    std::vector<Light> lights;
    if (!tc_scene_handle_valid(scene)) return lights;

    tc_component_cap_id light_cap = tc_light_capability_id();
    if (light_cap == TC_COMPONENT_CAPABILITY_INVALID_ID) return lights;

    tc_scene_foreach_with_capability(
        scene, light_cap, collect_lights_cap_cb, &lights,
        TC_SCENE_FILTER_ENABLED | TC_SCENE_FILTER_ENTITY_ENABLED);

    return lights;
}

} // namespace termin
