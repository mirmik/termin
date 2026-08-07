#include <termin/xr/xr_interaction_components.hpp>

#include <algorithm>
#include <cmath>
#include <limits>

#include <tc_inspect_cpp.hpp>
#include <tcbase/tc_log.h>
#include <termin/entity/component_registry.hpp>
#include <termin/input/tc_world_pointer_surface.h>
#include <termin/render/line_renderer.hpp>
#include <termin/tc_scene.hpp>
#include <termin/xr/xr_origin_component.hpp>

namespace termin {

namespace {

XrOriginComponent* find_origin_ancestor(Entity entity) {
    while (entity.valid()) {
        if (XrOriginComponent* origin = entity.get_component<XrOriginComponent>()) {
            return origin;
        }
        entity = entity.parent();
    }
    return nullptr;
}

void register_hand_field(tc::InspectFacetBuilder& inspect, const char* type_name) {
    tc::InspectFieldInfo info;
    info.type_name = type_name;
    info.path = "hand";
    info.label = "Hand";
    info.kind = "string";
    info.choices.push_back({"left", "Left"});
    info.choices.push_back({"right", "Right"});
    info.getter = [](void* obj) -> tc_value {
        return tc_value_string(static_cast<XrTrackedPoseComponent*>(obj)->get_hand_str().c_str());
    };
    info.setter = [](void* obj, tc_value value, void*) -> bool {
        if (value.type != TC_VALUE_STRING || !value.data.s) return false;
        static_cast<XrTrackedPoseComponent*>(obj)->set_hand_str(value.data.s);
        return true;
    };
    (void)inspect.add_field(std::move(info));
}

void register_pose_kind_field(tc::InspectFacetBuilder& inspect) {
    tc::InspectFieldInfo info;
    info.type_name = "XrTrackedPoseComponent";
    info.path = "pose_kind";
    info.label = "Pose";
    info.kind = "string";
    info.choices.push_back({"grip", "Grip"});
    info.choices.push_back({"aim", "Aim"});
    info.getter = [](void* obj) -> tc_value {
        return tc_value_string(static_cast<XrTrackedPoseComponent*>(obj)->get_pose_kind_str().c_str());
    };
    info.setter = [](void* obj, tc_value value, void*) -> bool {
        if (value.type != TC_VALUE_STRING || !value.data.s) return false;
        static_cast<XrTrackedPoseComponent*>(obj)->set_pose_kind_str(value.data.s);
        return true;
    };
    (void)inspect.add_field(std::move(info));
}

struct NearestWorldPointerSurface {
    const tc_world_pointer_ray* ray = nullptr;
    tc_component* component = nullptr;
    tc_world_pointer_hit hit{};
};

bool collect_nearest_world_pointer_surface(
    tc_component* component,
    void* userdata
) {
    auto* nearest = static_cast<NearestWorldPointerSurface*>(userdata);
    if (!nearest || !nearest->ray) return false;
    tc_world_pointer_hit hit{};
    if (!tc_world_pointer_surface_project_ray(
            component, nearest->ray, &hit) || !hit.inside) {
        return true;
    }
    if (!nearest->component || hit.distance < nearest->hit.distance) {
        nearest->component = component;
        nearest->hit = hit;
    }
    return true;
}

tc_component* resolve_world_pointer_surface(
    tc_entity_handle entity,
    const std::string& source_id
) {
    if (!tc_entity_handle_valid(entity) || source_id.empty()) return nullptr;
    const std::size_t count = tc_entity_component_count(entity);
    for (std::size_t index = 0; index < count; ++index) {
        tc_component* component = tc_entity_component_at(entity, index);
        const char* candidate_source_id =
            component ? tc_component_get_source_id(component) : nullptr;
        if (candidate_source_id && source_id == candidate_source_id &&
            tc_component_get_enabled(component) &&
            tc_component_has_capability(
                component, tc_world_pointer_surface_capability_id())) {
            return component;
        }
    }
    return nullptr;
}

bool same_world_pointer_surface(
    tc_component* component,
    tc_entity_handle entity,
    const std::string& source_id
) {
    if (!component || !tc_entity_handle_valid(entity)) return false;
    const char* component_source_id = tc_component_get_source_id(component);
    return tc_entity_handle_eq(component->owner, entity) &&
        component_source_id && source_id == component_source_id;
}

bool dispatch_world_pointer(
    tc_component* surface,
    std::uint64_t pointer_id,
    tc_world_pointer_phase phase,
    const tc_world_pointer_hit* hit,
    float pressure
) {
    if (!surface) return false;
    tc_world_pointer_event event{};
    event.pointer_id = pointer_id;
    event.phase = phase;
    event.u = hit ? hit->u : 0.0;
    event.v = hit ? hit->v : 0.0;
    event.pressure = pressure;
    return tc_world_pointer_surface_dispatch_pointer(surface, &event);
}

} // namespace

XrTrackedPoseComponent::XrTrackedPoseComponent()
    : CxxComponent("XrTrackedPoseComponent") {
    set_has_update(true);
    set_update_priority(lifecycle_priority::early);
}

void XrTrackedPoseComponent::register_type() {
    auto descriptor = ComponentTypeDescriptorBuilder::native<XrTrackedPoseComponent>(
        "XrTrackedPoseComponent", "termin-components-render", "CxxComponent");
    descriptor.category("Input");
    auto& inspect = descriptor.inspect();
    if (!inspect.find_field("XrTrackedPoseComponent", "input_device_id")) {
        inspect.add<XrTrackedPoseComponent, std::string>(
            "XrTrackedPoseComponent", &XrTrackedPoseComponent::input_device_id,
            "input_device_id", "Input Device", "string");
    }
    if (!inspect.find_field("XrTrackedPoseComponent", "hand")) register_hand_field(inspect, "XrTrackedPoseComponent");
    if (!inspect.find_field("XrTrackedPoseComponent", "pose_kind")) register_pose_kind_field(inspect);
    (void)descriptor.commit();
}

void XrTrackedPoseComponent::update(float) {
    tracking_active_ = false;
    if (!entity().valid()) return;

    xr::XrRigInputState* input = xr::XrInput::get_state(input_device_id);
    if (!input) {
        if (!logged_missing_input_) {
            tc_log_error("[XrTrackedPoseComponent] XR input device '%s' is not registered",
                         input_device_id.c_str());
            logged_missing_input_ = true;
        }
        return;
    }
    logged_missing_input_ = false;

    XrOriginComponent* origin = find_origin_ancestor(entity());
    if (!origin) {
        if (!logged_missing_origin_) {
            tc_log_error("[XrTrackedPoseComponent] entity '%s' is not under an XrOriginComponent",
                         entity().name());
            logged_missing_origin_ = true;
        }
        return;
    }
    logged_missing_origin_ = false;

    const xr::XrHandInputState& hand_state = input->hand(hand);
    const xr::XrPoseState& pose_state =
        pose_kind == XrTrackedPoseKind::Aim ? hand_state.aim_pose : hand_state.grip_pose;
    if (!pose_state.active) return;

    const Pose3 origin_world = origin->entity().transform().global_pose();
    entity().transform().set_global_pose(origin_world * pose_state.pose);
    tracking_active_ = true;
}

std::string XrTrackedPoseComponent::get_hand_str() const { return xr::xr_hand_to_string(hand); }
void XrTrackedPoseComponent::set_hand_str(const std::string& value) { hand = xr::xr_hand_from_string(value); }
std::string XrTrackedPoseComponent::get_pose_kind_str() const { return xr_tracked_pose_kind_to_string(pose_kind); }
void XrTrackedPoseComponent::set_pose_kind_str(const std::string& value) {
    pose_kind = xr_tracked_pose_kind_from_string(value);
}

XrGrabInteractableComponent::XrGrabInteractableComponent()
    : CxxComponent("XrGrabInteractableComponent") {}

void XrGrabInteractableComponent::register_type() {
    auto descriptor = ComponentTypeDescriptorBuilder::native<XrGrabInteractableComponent>(
        "XrGrabInteractableComponent", "termin-components-render", "CxxComponent");
    descriptor.category("Input");
    auto& inspect = descriptor.inspect();
    if (!inspect.find_field("XrGrabInteractableComponent", "grab_radius")) {
        inspect.add<XrGrabInteractableComponent, double>(
            "XrGrabInteractableComponent", &XrGrabInteractableComponent::grab_radius,
            "grab_radius", "Grab Radius", "double");
    }
    if (!inspect.find_field("XrGrabInteractableComponent", "grabbable")) {
        inspect.add<XrGrabInteractableComponent, bool>(
            "XrGrabInteractableComponent", &XrGrabInteractableComponent::grabbable,
            "grabbable", "Grabbable", "bool");
    }
    (void)descriptor.commit();
}

void XrGrabInteractableComponent::on_removed() {
    if (owner_) owner_->release_grabbed(this);
}

void XrGrabInteractableComponent::on_destroy() {
    if (owner_) owner_->release_grabbed(this);
}

XrDirectGrabInteractorComponent::XrDirectGrabInteractorComponent()
    : CxxComponent("XrDirectGrabInteractorComponent") {
    set_has_update(true);
}

void XrDirectGrabInteractorComponent::register_type() {
    auto descriptor = ComponentTypeDescriptorBuilder::native<XrDirectGrabInteractorComponent>(
        "XrDirectGrabInteractorComponent", "termin-components-render", "CxxComponent");
    descriptor.category("Input").require("XrTrackedPoseComponent");
    auto& inspect = descriptor.inspect();
    if (!inspect.find_field("XrDirectGrabInteractorComponent", "reach")) {
        inspect.add<XrDirectGrabInteractorComponent, double>(
            "XrDirectGrabInteractorComponent", &XrDirectGrabInteractorComponent::reach,
            "reach", "Reach", "double");
    }
    if (!inspect.find_field("XrDirectGrabInteractorComponent", "select_threshold")) {
        inspect.add<XrDirectGrabInteractorComponent, double>(
            "XrDirectGrabInteractorComponent", &XrDirectGrabInteractorComponent::select_threshold,
            "select_threshold", "Select Threshold", "double");
    }
    (void)descriptor.commit();
}

void XrDirectGrabInteractorComponent::update(float) {
    XrTrackedPoseComponent* tracker = entity().get_component<XrTrackedPoseComponent>();
    if (!tracker) {
        if (!logged_missing_tracker_) {
            tc_log_error("[XrDirectGrabInteractorComponent] entity '%s' has no XrTrackedPoseComponent",
                         entity().name());
            logged_missing_tracker_ = true;
        }
        release_grabbed();
        was_pressed_ = false;
        return;
    }
    logged_missing_tracker_ = false;

    xr::XrRigInputState* input = xr::XrInput::get_state(tracker->input_device_id);
    if (!input || !tracker->tracking_active()) {
        release_grabbed();
        was_pressed_ = false;
        return;
    }

    const bool pressed = input->hand(tracker->hand).select.pressed(
        std::clamp(select_threshold, 0.0, 1.0));
    const Pose3 hand_world_pose = entity().transform().global_pose();

    if (pressed && !was_pressed_ && !holding_object()) acquire_nearest(hand_world_pose);
    if (!pressed && holding_object()) release_grabbed();

    if (pressed && holding_object()) {
        XrGrabInteractableComponent* interactable =
            grabbed_entity_.get_component<XrGrabInteractableComponent>();
        if (!interactable || interactable->owner_ != this || !interactable->grabbable) {
            release_grabbed();
        } else {
            grabbed_entity_.transform().set_global_pose(hand_world_pose * hand_from_object_);
        }
    }
    was_pressed_ = pressed;
}

void XrDirectGrabInteractorComponent::acquire_nearest(const Pose3& hand_world_pose) {
    const double max_reach = std::max(0.0, reach);
    double nearest_distance = std::numeric_limits<double>::infinity();
    Entity nearest;

    for (Entity candidate : entity().scene().get_all_entities()) {
        if (!candidate.valid() || candidate == entity()) continue;
        XrGrabInteractableComponent* interactable = candidate.get_component<XrGrabInteractableComponent>();
        if (!interactable || !interactable->enabled() || !interactable->grabbable || interactable->owner_) continue;
        const double distance = (candidate.transform().global_position() - hand_world_pose.lin).norm();
        if (distance <= max_reach + std::max(0.0, interactable->grab_radius) && distance < nearest_distance) {
            nearest = candidate;
            nearest_distance = distance;
        }
    }

    if (!nearest.valid()) return;
    XrGrabInteractableComponent* interactable = nearest.get_component<XrGrabInteractableComponent>();
    if (!interactable) return;

    grabbed_entity_ = nearest;
    interactable->owner_ = this;
    hand_from_object_ = hand_world_pose.inverse() * nearest.transform().global_pose();
    tc_log_info("[XrDirectGrabInteractorComponent] '%s' grabbed '%s'",
                entity().name(), nearest.name());
}

void XrDirectGrabInteractorComponent::release_grabbed(XrGrabInteractableComponent* expected) {
    if (!grabbed_entity_.valid()) return;
    XrGrabInteractableComponent* interactable =
        grabbed_entity_.get_component<XrGrabInteractableComponent>();
    if (expected && interactable != expected) return;
    if (interactable && interactable->owner_ == this) interactable->owner_ = nullptr;
    tc_log_info("[XrDirectGrabInteractorComponent] '%s' released '%s'",
                entity().valid() ? entity().name() : "<detached>", grabbed_entity_.name());
    grabbed_entity_ = {};
}

void XrDirectGrabInteractorComponent::on_removed() { release_grabbed(); }
void XrDirectGrabInteractorComponent::on_destroy() { release_grabbed(); }
void XrDirectGrabInteractorComponent::on_scene_inactive() {
    release_grabbed();
    was_pressed_ = false;
}

XrRayInteractorComponent::XrRayInteractorComponent()
    : CxxComponent("XrRayInteractorComponent") {
    set_has_update(true);
}

void XrRayInteractorComponent::register_type() {
    auto descriptor =
        ComponentTypeDescriptorBuilder::native<XrRayInteractorComponent>(
            "XrRayInteractorComponent",
            "termin-components-render",
            "CxxComponent");
    descriptor.category("Input")
        .require("XrTrackedPoseComponent")
        .require("LineRenderer");
    auto& inspect = descriptor.inspect();
    inspect.add<XrRayInteractorComponent, double>(
        "XrRayInteractorComponent",
        &XrRayInteractorComponent::max_distance,
        "max_distance",
        "Max Distance",
        "double");
    inspect.add<XrRayInteractorComponent, double>(
        "XrRayInteractorComponent",
        &XrRayInteractorComponent::select_threshold,
        "select_threshold",
        "Select Threshold",
        "double");
    (void)descriptor.commit();
}

void XrRayInteractorComponent::update(float) {
    XrTrackedPoseComponent* tracker =
        entity().get_component<XrTrackedPoseComponent>();
    LineRenderer* line = entity().get_component<LineRenderer>();
    if (!tracker) {
        if (!logged_missing_tracker_) {
            tc_log_error(
                "[XrRayInteractorComponent] entity '%s' has no "
                "XrTrackedPoseComponent",
                entity().name());
            logged_missing_tracker_ = true;
        }
        reset_interaction(true, true);
        was_pressed_ = false;
        return;
    }
    logged_missing_tracker_ = false;
    if (!line) {
        if (!logged_missing_line_renderer_) {
            tc_log_error(
                "[XrRayInteractorComponent] entity '%s' has no LineRenderer",
                entity().name());
            logged_missing_line_renderer_ = true;
        }
        reset_interaction(true, true);
        was_pressed_ = false;
        return;
    }
    logged_missing_line_renderer_ = false;

    xr::XrRigInputState* input =
        xr::XrInput::get_state(tracker->input_device_id);
    if (!input || !tracker->tracking_active()) {
        reset_interaction(true, true);
        was_pressed_ = false;
        return;
    }

    const double ray_limit = std::max(0.0, max_distance);
    const Pose3 aim_pose = entity().transform().global_pose();
    const Vec3 direction = aim_pose.transform_vector({0.0, 1.0, 0.0}).normalized();
    const tc_world_pointer_ray ray{
        .origin_x = aim_pose.lin.x,
        .origin_y = aim_pose.lin.y,
        .origin_z = aim_pose.lin.z,
        .direction_x = direction.x,
        .direction_y = direction.y,
        .direction_z = direction.z,
        .max_distance = ray_limit,
    };
    const xr::XrScalarState& select = input->hand(tracker->hand).select;
    const bool pressed = select.pressed(
        std::clamp(select_threshold, 0.0, 1.0));
    const std::uint64_t pointer_id = entity().runtime_id();
    pointing_ = true;
    visible_ray_length_ = ray_limit;

    tc_component* captured = resolve_world_pointer_surface(
        captured_surface_.entity, captured_surface_.source_id);
    if (captured_surface_.valid() && !captured) {
        captured_surface_.clear();
    }

    if (captured) {
        tc_world_pointer_hit hit{};
        if (!tc_world_pointer_surface_project_ray(captured, &ray, &hit)) {
            dispatch_world_pointer(
                captured, pointer_id, TC_WORLD_POINTER_CANCEL, nullptr, 0.0f);
            captured_surface_.clear();
            hovered_surface_.clear();
        } else {
            visible_ray_length_ = hit.distance;
            dispatch_world_pointer(
                captured,
                pointer_id,
                TC_WORLD_POINTER_MOVE,
                &hit,
                static_cast<float>(select.value));
            if (!pressed) {
                dispatch_world_pointer(
                    captured,
                    pointer_id,
                    TC_WORLD_POINTER_UP,
                    &hit,
                    0.0f);
                captured_surface_.clear();
                if (!hit.inside) hovered_surface_.clear();
            }
        }
    } else {
        NearestWorldPointerSurface nearest;
        nearest.ray = &ray;
        tc_scene_foreach_with_capability(
            entity().scene().handle(),
            tc_world_pointer_surface_capability_id(),
            collect_nearest_world_pointer_surface,
            &nearest,
            TC_SCENE_FILTER_ENABLED | TC_SCENE_FILTER_ENTITY_ENABLED);

        tc_component* hovered = resolve_world_pointer_surface(
            hovered_surface_.entity, hovered_surface_.source_id);
        const bool same_hover = nearest.component && hovered &&
            same_world_pointer_surface(
                nearest.component,
                hovered_surface_.entity,
                hovered_surface_.source_id);
        if (hovered && !same_hover) {
            dispatch_world_pointer(
                hovered, pointer_id, TC_WORLD_POINTER_LEAVE, nullptr, 0.0f);
            hovered_surface_.clear();
        }

        if (nearest.component) {
            visible_ray_length_ = nearest.hit.distance;
            const char* source_id =
                tc_component_ensure_source_id(nearest.component);
            if (!source_id || source_id[0] == '\0') {
                tc_log_error(
                    "[XrRayInteractorComponent] world-pointer surface on '%s' "
                    "has no stable source id",
                    tc_entity_name(nearest.component->owner));
            } else {
                hovered_surface_.entity = nearest.component->owner;
                hovered_surface_.source_id = source_id;
                dispatch_world_pointer(
                    nearest.component,
                    pointer_id,
                    TC_WORLD_POINTER_MOVE,
                    &nearest.hit,
                    static_cast<float>(select.value));
                if (pressed && !was_pressed_ &&
                    dispatch_world_pointer(
                        nearest.component,
                        pointer_id,
                        TC_WORLD_POINTER_DOWN,
                        &nearest.hit,
                        static_cast<float>(select.value))) {
                    captured_surface_ = hovered_surface_;
                }
            }
        }
    }

    line->set_segment(
        tc_vec3{0.0, 0.0, 0.0},
        tc_vec3{0.0, visible_ray_length_, 0.0});
    was_pressed_ = pressed;
}

void XrRayInteractorComponent::reset_interaction(
    bool cancel_capture,
    bool clear_runtime_visual
) {
    const std::uint64_t pointer_id = entity().valid()
        ? entity().runtime_id()
        : 0;
    tc_component* captured = resolve_world_pointer_surface(
        captured_surface_.entity, captured_surface_.source_id);
    tc_component* hovered = resolve_world_pointer_surface(
        hovered_surface_.entity, hovered_surface_.source_id);
    if (captured && cancel_capture) {
        dispatch_world_pointer(
            captured, pointer_id, TC_WORLD_POINTER_CANCEL, nullptr, 0.0f);
    } else if (hovered) {
        dispatch_world_pointer(
            hovered, pointer_id, TC_WORLD_POINTER_LEAVE, nullptr, 0.0f);
    }
    captured_surface_.clear();
    hovered_surface_.clear();
    pointing_ = false;
    visible_ray_length_ = 0.0;
    if (clear_runtime_visual && entity().valid()) {
        if (LineRenderer* line = entity().get_component<LineRenderer>()) {
            line->clear_points();
        }
    }
}

void XrRayInteractorComponent::on_removed() {
    reset_interaction(true, false);
}
void XrRayInteractorComponent::on_destroy() {
    reset_interaction(true, false);
}
void XrRayInteractorComponent::on_scene_inactive() {
    reset_interaction(true, false);
    was_pressed_ = false;
}

const char* xr_tracked_pose_kind_to_string(XrTrackedPoseKind kind) {
    return kind == XrTrackedPoseKind::Aim ? "aim" : "grip";
}

XrTrackedPoseKind xr_tracked_pose_kind_from_string(const std::string& value) {
    return value == "aim" ? XrTrackedPoseKind::Aim : XrTrackedPoseKind::Grip;
}

} // namespace termin
