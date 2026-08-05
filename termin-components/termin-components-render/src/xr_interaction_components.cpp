#include <termin/xr/xr_interaction_components.hpp>

#include <algorithm>
#include <limits>

#include <tc_inspect_cpp.hpp>
#include <tcbase/tc_log.h>
#include <termin/entity/component_registry.hpp>
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

const char* xr_tracked_pose_kind_to_string(XrTrackedPoseKind kind) {
    return kind == XrTrackedPoseKind::Aim ? "aim" : "grip";
}

XrTrackedPoseKind xr_tracked_pose_kind_from_string(const std::string& value) {
    return value == "aim" ? XrTrackedPoseKind::Aim : XrTrackedPoseKind::Grip;
}

} // namespace termin
