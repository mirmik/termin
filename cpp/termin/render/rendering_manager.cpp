// rendering_manager.cpp - Global rendering manager implementation
#include "termin/render/rendering_manager.hpp"
#include "termin/render/scene_pipeline_template.hpp"
#include "termin/camera/camera_component.hpp"
#include "termin/lighting/light_component.hpp"
#include "termin/entity/entity.hpp"
#include "termin/viewport/tc_viewport_handle.hpp"

extern "C" {
#include "tc_log.h"
#include "core/tc_scene.h"
#include "core/tc_scene_pool.h"
#include "core/tc_entity_pool.h"
#include "core/tc_entity_pool_registry.h"
#include "tc_viewport_config.h"
#include "render/tc_viewport_pool.h"
#include "render/tc_rendering_manager.h"
}

#include <algorithm>

namespace termin {

// Helper to make a unique key from viewport handle
static inline uint64_t viewport_key(tc_viewport_handle h) {
    return (static_cast<uint64_t>(h.index) << 32) | h.generation;
}

// ============================================================================
// Singleton - uses C API to ensure single instance across all DLLs
// ============================================================================

RenderingManager* RenderingManager::s_instance = nullptr;

RenderingManager& RenderingManager::instance() {
    // Check global storage in entity_lib first
    RenderingManager* global = reinterpret_cast<RenderingManager*>(tc_rendering_manager_instance());
    if (global) {
        s_instance = global;  // Cache locally
        return *global;
    }

    // Create new instance and store globally
    if (!s_instance) {
        s_instance = new RenderingManager();
        tc_rendering_manager_set_instance(reinterpret_cast<tc_rendering_manager*>(s_instance));
    }
    return *s_instance;
}

void RenderingManager::reset_for_testing() {
    if (s_instance) {
        delete s_instance;
        s_instance = nullptr;
        tc_rendering_manager_set_instance(nullptr);
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

void RenderingManager::set_make_current_callback(MakeCurrentCallback callback) {
    make_current_callback_ = std::move(callback);
}

void RenderingManager::set_display_factory(DisplayFactory factory) {
    display_factory_ = std::move(factory);
}

void RenderingManager::set_pipeline_factory(PipelineFactory factory) {
    pipeline_factory_ = std::move(factory);
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

    displays_.erase(it);
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
    CameraComponent* camera,
    float region_x, float region_y, float region_w, float region_h,
    RenderPipeline* pipeline,
    const std::string& name
) {
    if (!tc_scene_handle_valid(scene) || !display || !camera) {
        return TC_VIEWPORT_HANDLE_INVALID;
    }

    // Create viewport
    tc_viewport_handle viewport = tc_viewport_new(
        name.c_str(),
        scene,
        camera->tc_component_ptr()
    );

    if (!tc_viewport_handle_valid(viewport)) {
        tc_log(TC_LOG_ERROR, "[RenderingManager] Failed to create viewport '%s'", name.c_str());
        return TC_VIEWPORT_HANDLE_INVALID;
    }

    // Set rect
    tc_viewport_set_rect(viewport, region_x, region_y, region_w, region_h);

    // Set pipeline if provided
    if (pipeline) {
        tc_viewport_set_pipeline(viewport, pipeline->handle());
    }

    // Add to display
    tc_display_add_viewport(display, viewport);

    // Register viewport with camera
    camera->add_viewport(TcViewport(viewport));

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
        // Remove from camera
        tc_component* camera_comp = tc_viewport_get_camera(viewport);
        if (camera_comp) {
            CxxComponent* cxx = CxxComponent::from_tc(camera_comp);
            CameraComponent* camera = cxx ? static_cast<CameraComponent*>(cxx) : nullptr;
            if (camera) {
                camera->remove_viewport(TcViewport(viewport));
            }
        }

        // Remove viewport state
        remove_viewport_state(viewport);

        // Remove from display
        tc_display_remove_viewport(display, viewport);

        // Free viewport
        tc_viewport_free(viewport);
    }
}

// Helper struct for camera search callback
struct CameraSearchData {
    tc_entity_pool* pool;
    CameraComponent* camera;
    const char* found_name;
};

static bool find_first_camera_cb(tc_entity_pool* pool, tc_entity_id id, void* user_data) {
    CameraSearchData* data = static_cast<CameraSearchData*>(user_data);

    // Get entity handle
    tc_entity_pool_handle pool_handle = tc_entity_pool_registry_find(pool);
    tc_entity_handle eh = tc_entity_handle_make(pool_handle, id);
    Entity entity(eh);

    CameraComponent* cam = entity.get_component<CameraComponent>();
    if (cam) {
        data->camera = cam;
        data->found_name = tc_entity_pool_name(pool, id);
        return false; // Stop iteration
    }
    return true; // Continue
}

std::vector<tc_viewport_handle> RenderingManager::attach_scene_full(tc_scene_handle scene) {
    std::vector<tc_viewport_handle> viewports;

    if (!tc_scene_handle_valid(scene)) {
        tc_log(TC_LOG_ERROR, "[RenderingManager] attach_scene_full: invalid scene handle");
        return viewports;
    }

    size_t config_count = tc_scene_viewport_config_count(scene);
    tc_entity_pool* pool = tc_scene_entity_pool(scene);
    tc_entity_pool_handle pool_handle = pool ? tc_entity_pool_registry_find(pool) : TC_ENTITY_POOL_HANDLE_INVALID;

    for (size_t i = 0; i < config_count; i++) {
        tc_viewport_config* config = tc_scene_viewport_config_at(scene, i);
        if (!config) continue;

        // Get or create display
        std::string display_name = config->display_name ? config->display_name : "Main";
        tc_display* display = get_or_create_display(display_name);
        if (!display) {
            tc_log(TC_LOG_WARN, "[RenderingManager] Cannot create display '%s' for scene viewport",
                   display_name.c_str());
            continue;
        }

        // Find camera by UUID
        CameraComponent* camera = nullptr;
        if (config->camera_uuid && config->camera_uuid[0] != '\0' && pool) {
            tc_entity_id eid = tc_entity_pool_find_by_uuid(pool, config->camera_uuid);
            if (tc_entity_id_valid(eid)) {
                tc_entity_handle eh = tc_entity_handle_make(pool_handle, eid);
                Entity entity(eh);
                camera = entity.get_component<CameraComponent>();
            }
            if (!camera) {
                tc_log(TC_LOG_WARN, "[RenderingManager] Camera entity not found for uuid=%s",
                       config->camera_uuid);
            }
        }

        // Fallback: find first camera in scene using iterator
        if (!camera && pool) {
            CameraSearchData search_data{pool, nullptr, nullptr};
            tc_entity_pool_foreach(pool, find_first_camera_cb, &search_data);
            if (search_data.camera) {
                camera = search_data.camera;
                tc_log(TC_LOG_WARN, "[RenderingManager] Using fallback camera from entity '%s'",
                       search_data.found_name ? search_data.found_name : "?");
            }
        }

        if (!camera) {
            tc_log(TC_LOG_WARN, "[RenderingManager] No camera found for viewport on display '%s'",
                   display_name.c_str());
            continue;
        }

        // Get pipeline
        RenderPipeline* pipeline = nullptr;

        // Try by UUID first
        if (config->pipeline_uuid && config->pipeline_uuid[0] != '\0') {
            // TODO: lookup pipeline by UUID from ResourceManager
            // For now, skip UUID lookup
        }

        // Try by name via factory
        if (!pipeline && config->pipeline_name && config->pipeline_name[0] != '\0') {
            if (pipeline_factory_) {
                pipeline = pipeline_factory_(config->pipeline_name);
                if (!pipeline) {
                    tc_log(TC_LOG_WARN, "[RenderingManager] Pipeline factory returned null for name=%s",
                           config->pipeline_name);
                }
            } else {
                tc_log(TC_LOG_WARN, "[RenderingManager] No pipeline factory set for name=%s",
                       config->pipeline_name);
            }
        }

        // Create viewport
        std::string vp_name = config->name ? config->name : "";
        tc_viewport_handle viewport = mount_scene(
            scene,
            display,
            camera,
            config->region[0], config->region[1], config->region[2], config->region[3],
            pipeline,
            vp_name
        );

        if (!tc_viewport_handle_valid(viewport)) {
            continue;
        }

        // Apply additional properties
        tc_viewport_set_depth(viewport, config->depth);
        tc_viewport_set_enabled(viewport, config->enabled);
        tc_viewport_set_layer_mask(viewport, config->layer_mask);
        if (config->input_mode) {
            tc_viewport_set_input_mode(viewport, config->input_mode);
        }
        tc_viewport_set_block_input_in_editor(viewport, config->block_input_in_editor);

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
    size_t template_count = tc_scene_pipeline_template_count(scene);
    for (size_t i = 0; i < template_count; i++) {
        tc_spt_handle spt_handle = tc_scene_pipeline_template_at(scene, i);
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

    // Activate GL context via callback
    if (make_current_callback_) {
        make_current_callback_();
    }

    RenderEngine* engine = render_engine();
    if (!engine) {
        tc_log(TC_LOG_WARN, "[RenderingManager] render_all_offscreen: no render engine");
        return;
    }

    // 1. Execute scene pipelines (can span multiple displays)
    for (tc_scene_handle scene : attached_scenes_) {
        if (!tc_scene_handle_valid(scene)) continue;

        std::vector<std::string> pipeline_names = get_pipeline_names(scene);
        for (const std::string& pipeline_name : pipeline_names) {
            RenderPipeline* pipeline = get_scene_pipeline(scene, pipeline_name);
            if (pipeline) {
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
}

void RenderingManager::render_scene_pipeline_offscreen(
    tc_scene_handle scene,
    const std::string& pipeline_name,
    RenderPipeline* pipeline
) {
    if (!tc_scene_handle_valid(scene) || !pipeline || !graphics_) {
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

        CxxComponent* cxx = CxxComponent::from_tc(camera_comp);
        CameraComponent* camera = cxx ? static_cast<CameraComponent*>(cxx) : nullptr;
        if (!camera) {
            tc_log(TC_LOG_WARN, "[RenderingManager] Viewport '%s' camera is not CxxComponent", vp_name.c_str());
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

        // Ensure output FBO
        ViewportRenderState* state = get_or_create_viewport_state(viewport);
        FramebufferHandle* output_fbo = state->ensure_output_fbo(graphics_, pw, ph);

        // Update camera aspect ratio
        camera->set_aspect(static_cast<double>(pw) / std::max(1, ph));

        // Create viewport context
        ViewportContext ctx;
        ctx.name = vp_name;
        ctx.camera = camera;
        ctx.rect = {0, 0, pw, ph};  // Full FBO, offset at blit time
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
    engine->render_scene_pipeline_offscreen(
        pipeline,
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

    tc_scene_handle scene = tc_viewport_get_scene(viewport);
    tc_component* camera_comp = tc_viewport_get_camera(viewport);
    tc_pipeline_handle pipeline = tc_viewport_get_pipeline(viewport);

    if (!tc_scene_handle_valid(scene)) {
        tc_log(TC_LOG_WARN, "[RenderingManager] render_viewport_offscreen('%s'): invalid scene",
               vp_name ? vp_name : "(null)");
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

    // Get RenderPipeline from pipeline handle
    RenderPipeline* render_pipeline = RenderPipeline::from_handle(pipeline);
    if (!render_pipeline) {
        tc_log(TC_LOG_WARN, "[RenderingManager] render_viewport_offscreen('%s'): RenderPipeline::from_handle returned null",
               vp_name ? vp_name : "(null)");
        return;
    }

    // Get CameraComponent from tc_component using container_of pattern
    CxxComponent* cxx = CxxComponent::from_tc(camera_comp);
    CameraComponent* camera = cxx ? static_cast<CameraComponent*>(cxx) : nullptr;
    if (!camera) {
        tc_log(TC_LOG_WARN, "[RenderingManager] render_viewport_offscreen('%s'): CxxComponent::from_tc failed",
               vp_name ? vp_name : "(null)");
        return;
    }

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

    // Clear existing pipelines first (calls notify_render_detach)
    detach_scene(scene);

    size_t template_count = tc_scene_pipeline_template_count(scene);
    uint64_t key = scene_key(scene);

    for (size_t i = 0; i < template_count; i++) {
        tc_spt_handle spt_handle = tc_scene_pipeline_template_at(scene, i);
        if (!tc_spt_is_valid(spt_handle)) continue;

        TcScenePipelineTemplate templ(spt_handle);
        if (!templ.is_loaded()) {
            tc_log(TC_LOG_WARN, "[RenderingManager] Template not loaded: '%s'", templ.name().c_str());
            continue;
        }

        RenderPipeline* pipeline = templ.compile();
        if (!pipeline) {
            tc_log(TC_LOG_WARN, "[RenderingManager] Failed to compile template: '%s'", templ.name().c_str());
            continue;
        }

        std::string name = templ.name();
        pipeline->set_name(name);

        // Store ownership in scene_pipelines_
        scene_pipelines_[key][name] = std::unique_ptr<RenderPipeline>(pipeline);

        // Store targets
        pipeline_targets_[name] = templ.target_viewports();
    }

    // Notify components that rendering is attached
    tc_scene_notify_render_attach(scene);
}

void RenderingManager::detach_scene(tc_scene_handle scene) {
    if (!tc_scene_handle_valid(scene)) return;
    clear_scene_pipelines(scene);
}

RenderPipeline* RenderingManager::get_scene_pipeline(tc_scene_handle scene, const std::string& name) const {
    if (!tc_scene_handle_valid(scene)) return nullptr;
    uint64_t key = scene_key(scene);
    auto scene_it = scene_pipelines_.find(key);
    if (scene_it == scene_pipelines_.end()) return nullptr;
    auto pipe_it = scene_it->second.find(name);
    return (pipe_it != scene_it->second.end()) ? pipe_it->second.get() : nullptr;
}

RenderPipeline* RenderingManager::get_scene_pipeline(const std::string& name) const {
    // Search all scenes
    for (const auto& [key, pipelines] : scene_pipelines_) {
        auto it = pipelines.find(name);
        if (it != pipelines.end()) {
            return it->second.get();
        }
    }
    tc_log(TC_LOG_WARN, "[RenderingManager] get_scene_pipeline NOT FOUND: '%s'", name.c_str());
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

    // Erase the scene entry (unique_ptrs will delete pipelines)
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

    // Clear all (unique_ptrs will delete pipelines)
    scene_pipelines_.clear();
    pipeline_targets_.clear();
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

    // Clear attached scenes
    attached_scenes_.clear();

    // Clear scene pipelines (deletes owned pipelines)
    clear_all_scene_pipelines();

    // Clear displays (don't free them - we don't own them)
    displays_.clear();

    // Clear callbacks
    make_current_callback_ = nullptr;
    display_factory_ = nullptr;
    pipeline_factory_ = nullptr;

    // Release owned render engine
    owned_render_engine_.reset();
    render_engine_ = nullptr;

    graphics_ = nullptr;
}

// ============================================================================
// Helpers
// ============================================================================

// Helper struct for light collection callback
struct LightCollectData {
    tc_entity_pool* pool;
    std::vector<Light>* lights;
};

static bool collect_lights_cb(tc_entity_pool* pool, tc_entity_id id, void* user_data) {
    LightCollectData* data = static_cast<LightCollectData*>(user_data);

    // Get entity handle
    tc_entity_pool_handle pool_handle = tc_entity_pool_registry_find(pool);
    tc_entity_handle eh = tc_entity_handle_make(pool_handle, id);
    Entity entity(eh);

    LightComponent* light = entity.get_component<LightComponent>();
    if (light) {
        data->lights->push_back(light->to_light());
    }
    return true; // Continue iteration
}

std::vector<Light> RenderingManager::collect_lights(tc_scene_handle scene) {
    std::vector<Light> lights;

    if (!tc_scene_handle_valid(scene)) {
        return lights;
    }

    tc_entity_pool* pool = tc_scene_entity_pool(scene);
    if (!pool) {
        return lights;
    }

    LightCollectData data{pool, &lights};
    tc_entity_pool_foreach(pool, collect_lights_cb, &data);

    return lights;
}

} // namespace termin
