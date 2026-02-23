#include "camera_viewport_component.hpp"
#include "camera_component.hpp"
#include "../render/rendering_manager.hpp"
#include "tc_inspect_cpp.hpp"
#include <tcbase/tc_log.hpp>

extern "C" {
#include "render/tc_display.h"
#include "render/tc_viewport.h"
#include "render/tc_viewport_input_manager.h"
}

namespace termin {

// --- layer_mask field: needs kind="layer_mask" so we register manually ---
static struct _CameraViewportLayerMaskRegistrar {
    _CameraViewportLayerMaskRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "CameraViewportComponent";
        info.path = "layer_mask";
        info.label = "Layers";
        info.kind = "layer_mask";

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<CameraViewportComponent*>(obj);
            // tc_value doesn't have uint64, so use string hex
            char buf[32];
            snprintf(buf, sizeof(buf), "0x%llx", (unsigned long long)c->layer_mask);
            return tc_value_string(buf);
        };

        info.setter = [](void* obj, tc_value value, tc_scene_handle) {
            auto* c = static_cast<CameraViewportComponent*>(obj);
            if (value.type == TC_VALUE_STRING && value.data.s) {
                c->layer_mask = strtoull(value.data.s, nullptr, 0);
            } else if (value.type == TC_VALUE_INT) {
                c->layer_mask = static_cast<uint64_t>(value.data.i);
            }
        };

        tc::InspectRegistry::instance().add_field_with_choices(
            "CameraViewportComponent", std::move(info));
    }
} _camera_viewport_layer_mask_registrar;

// ---------------------------------------------------------------------------
// Constructor
// ---------------------------------------------------------------------------

CameraViewportComponent::CameraViewportComponent() {
    link_type_entry("CameraViewportComponent");
    set_active_in_editor(true);
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

void CameraViewportComponent::on_render_attach() {
    setup_viewport();
}

void CameraViewportComponent::on_render_detach() {
    // Free viewport input manager
    if (viewport_input_manager_) {
        tc_viewport_input_manager_free(viewport_input_manager_);
        viewport_input_manager_ = nullptr;
    }

    // Clear camera on viewport so renderer skips it until next attach
    if (viewport_.is_valid()) {
        tc_viewport_set_camera(viewport_.handle_, nullptr);
    }
    // Release reference without destroying — viewport persists on display
    // for reuse on next on_render_attach (e.g. editor→game mode transition)
    viewport_ = TcViewport();
    display_ = nullptr;
}

void CameraViewportComponent::on_destroy() {
    teardown_viewport();
}

// ---------------------------------------------------------------------------
// Core logic
// ---------------------------------------------------------------------------

CameraComponent* CameraViewportComponent::find_camera() const {
    Entity ent = entity();
    if (!ent.valid()) return nullptr;
    return ent.get_component<CameraComponent>();
}

void CameraViewportComponent::setup_viewport() {
    if (viewport_.is_valid()) return;  // already set up

    CameraComponent* camera = find_camera();
    if (!camera) {
        tc_log(TC_LOG_WARN,
               "[CameraViewportComponent] No CameraComponent found on entity");
        return;
    }

    // Find or create display via RenderingManager
    RenderingManager& rm = RenderingManager::instance();
    tc_display* display = rm.get_or_create_display(target_display);
    if (!display) {
        tc_log(TC_LOG_WARN,
               "[CameraViewportComponent] Display '%s' not found",
               target_display.c_str());
        return;
    }
    display_ = display;

    // Ensure display has a router for event routing to viewports
    rm.ensure_display_router(display);

    // Build viewport name from entity
    std::string vp_name = "CameraViewport";
    Entity ent = entity();
    if (ent.valid()) {
        const char* ename = ent.name();
        if (ename && ename[0]) {
            vp_name = std::string("CameraViewport_") + ename;
        }
    }

    // Get scene from entity's pool
    tc_scene_handle scene = TC_SCENE_HANDLE_INVALID;
    if (ent.valid()) {
        tc_entity_pool* pool = ent.pool_ptr();
        if (pool) {
            scene = tc_entity_pool_get_scene(pool);
        }
    }

    // Try to reuse existing viewport by name (survives editor→game mode transitions)
    size_t vp_count = tc_display_get_viewport_count(display);
    for (size_t i = 0; i < vp_count; ++i) {
        tc_viewport_handle vh = tc_display_get_viewport_at_index(display, i);
        if (!tc_viewport_alive(vh)) continue;
        const char* name = tc_viewport_get_name(vh);
        if (name && vp_name == name) {
            viewport_ = TcViewport(vh);
            // Update camera and scene to point to current instances
            tc_viewport_set_camera(vh, camera->tc_component_ptr());
            tc_viewport_set_scene(vh, scene);
            apply_settings();
            // Attach input manager if not already set
            if (!tc_viewport_get_input_manager(vh) && input_manager_type == "simple") {
                viewport_input_manager_ = tc_viewport_input_manager_new(vh);
            }
            return;
        }
    }

    // Resolve pipeline via factory
    RenderPipeline* pipeline = nullptr;
    if (!pipeline_name.empty()) {
        pipeline = rm.create_pipeline(pipeline_name);
    }

    tc_viewport_handle vh = rm.mount_scene(
        scene, display, camera,
        rect_x, rect_y, rect_w, rect_h,
        pipeline, vp_name);

    if (!tc_viewport_handle_valid(vh)) {
        tc_log(TC_LOG_ERROR,
               "[CameraViewportComponent] Failed to create viewport");
        return;
    }

    viewport_ = TcViewport(vh);
    apply_settings();

    // Attach input manager based on type
    if (input_manager_type == "simple") {
        viewport_input_manager_ = tc_viewport_input_manager_new(vh);
    }
}

void CameraViewportComponent::apply_settings() {
    if (!viewport_.is_valid()) return;

    tc_viewport_handle vh = viewport_.handle_;
    tc_viewport_set_rect(vh, rect_x, rect_y, rect_w, rect_h);
    tc_viewport_set_depth(vh, depth);
    tc_viewport_set_layer_mask(vh, layer_mask);

    // Update pixel rect if display known
    if (display_) {
        int w = 0, h = 0;
        tc_display_get_size(display_, &w, &h);
        viewport_.update_pixel_rect(w, h);
    }
}

void CameraViewportComponent::apply_display() {
    // Migrate viewport to the display specified by target_display.
    // If already on that display, do nothing.
    RenderingManager& rm = RenderingManager::instance();
    tc_display* target = rm.get_display_by_name(target_display);
    if (target == display_ && target != nullptr) return;  // already there

    tc_display* old_display = display_;
    teardown_viewport();
    setup_viewport();

    // Try to auto-remove old display if empty and flagged
    if (old_display && old_display != display_) {
        rm.try_auto_remove_display(old_display);
    }
}

void CameraViewportComponent::set_target_display(const std::string& new_name) {
    if (new_name == target_display) return;
    target_display = new_name;
    apply_display();
}

void CameraViewportComponent::teardown_viewport() {
    // Free viewport input manager
    if (viewport_input_manager_) {
        tc_viewport_input_manager_free(viewport_input_manager_);
        viewport_input_manager_ = nullptr;
    }

    if (viewport_.is_valid() && display_) {
        // Remove from camera
        CameraComponent* camera = find_camera();
        if (camera) {
            camera->remove_viewport(viewport_);
        }

        // Remove from display
        tc_display_remove_viewport(display_, viewport_.handle_);

        // Cleanup render state
        RenderingManager& rm = RenderingManager::instance();
        rm.remove_viewport_state(viewport_.handle_);

        // Destroy viewport
        viewport_.destroy();
    }
    viewport_ = TcViewport();
    display_ = nullptr;
}

} // namespace termin
