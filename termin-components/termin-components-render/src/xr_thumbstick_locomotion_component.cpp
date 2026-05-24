#include <termin/xr/xr_thumbstick_locomotion_component.hpp>

#include <algorithm>
#include <cmath>

#include <tc_inspect_cpp.hpp>
#include <tcbase/tc_log.h>
#include <termin/entity/component_registry.hpp>
#include <termin/geom/general_pose3.hpp>
#include <termin/geom/quat.hpp>
#include <termin/xr/xr_origin_component.hpp>

namespace termin {

namespace {

constexpr double kPi = 3.14159265358979323846;

Vec3 projected_normalized(Vec3 v, const Vec3& fallback) {
    v.z = 0.0;
    const double len = v.norm();
    if (len < 1e-6) {
        return fallback;
    }
    return v / len;
}

} // namespace

XrThumbstickLocomotionComponent::XrThumbstickLocomotionComponent()
    : CxxComponent("XrThumbstickLocomotionComponent")
{
    set_has_update(true);
}

void XrThumbstickLocomotionComponent::register_type() {
    auto& component_registry = ComponentRegistry::instance();
    if (!component_registry.has("XrThumbstickLocomotionComponent")) {
        component_registry.register_native(
            "XrThumbstickLocomotionComponent",
            &CxxComponentFactoryData<XrThumbstickLocomotionComponent>::create,
            nullptr,
            "Component"
        );
    }

    auto& inspect = tc::InspectRegistry::instance();
    inspect.set_type_parent("XrThumbstickLocomotionComponent", "Component");
    if (!inspect.find_field("XrThumbstickLocomotionComponent", "input_device_id")) {
        inspect.add<XrThumbstickLocomotionComponent, std::string>(
            "XrThumbstickLocomotionComponent",
            &XrThumbstickLocomotionComponent::input_device_id,
            "input_device_id",
            "Input Device",
            "string"
        );
    }
    if (!inspect.find_field("XrThumbstickLocomotionComponent", "move_speed")) {
        inspect.add<XrThumbstickLocomotionComponent, double>(
            "XrThumbstickLocomotionComponent",
            &XrThumbstickLocomotionComponent::move_speed,
            "move_speed",
            "Move Speed",
            "double"
        );
    }
    if (!inspect.find_field("XrThumbstickLocomotionComponent", "speed_multiplier")) {
        inspect.add<XrThumbstickLocomotionComponent, double>(
            "XrThumbstickLocomotionComponent",
            &XrThumbstickLocomotionComponent::speed_multiplier,
            "speed_multiplier",
            "Speed Multiplier",
            "double"
        );
    }
    if (!inspect.find_field("XrThumbstickLocomotionComponent", "deadzone")) {
        inspect.add<XrThumbstickLocomotionComponent, double>(
            "XrThumbstickLocomotionComponent",
            &XrThumbstickLocomotionComponent::deadzone,
            "deadzone",
            "Deadzone",
            "double"
        );
    }
    if (!inspect.find_field("XrThumbstickLocomotionComponent", "normalize_diagonal")) {
        inspect.add<XrThumbstickLocomotionComponent, bool>(
            "XrThumbstickLocomotionComponent",
            &XrThumbstickLocomotionComponent::normalize_diagonal,
            "normalize_diagonal",
            "Normalize Diagonal",
            "bool"
        );
    }
    if (!inspect.find_field("XrThumbstickLocomotionComponent", "scale_after_deadzone")) {
        inspect.add<XrThumbstickLocomotionComponent, bool>(
            "XrThumbstickLocomotionComponent",
            &XrThumbstickLocomotionComponent::scale_after_deadzone,
            "scale_after_deadzone",
            "Scale After Deadzone",
            "bool"
        );
    }
    if (!inspect.find_field("XrThumbstickLocomotionComponent", "invert_x")) {
        inspect.add<XrThumbstickLocomotionComponent, bool>(
            "XrThumbstickLocomotionComponent",
            &XrThumbstickLocomotionComponent::invert_x,
            "invert_x",
            "Invert X",
            "bool"
        );
    }
    if (!inspect.find_field("XrThumbstickLocomotionComponent", "invert_y")) {
        inspect.add<XrThumbstickLocomotionComponent, bool>(
            "XrThumbstickLocomotionComponent",
            &XrThumbstickLocomotionComponent::invert_y,
            "invert_y",
            "Invert Y",
            "bool"
        );
    }
    if (!inspect.find_field("XrThumbstickLocomotionComponent", "continuous_turn_enabled")) {
        inspect.add<XrThumbstickLocomotionComponent, bool>(
            "XrThumbstickLocomotionComponent",
            &XrThumbstickLocomotionComponent::continuous_turn_enabled,
            "continuous_turn_enabled",
            "Continuous Turn",
            "bool"
        );
    }
    if (!inspect.find_field("XrThumbstickLocomotionComponent", "turn_speed_degrees")) {
        inspect.add<XrThumbstickLocomotionComponent, double>(
            "XrThumbstickLocomotionComponent",
            &XrThumbstickLocomotionComponent::turn_speed_degrees,
            "turn_speed_degrees",
            "Turn Speed",
            "double"
        );
    }
    if (!inspect.find_field("XrThumbstickLocomotionComponent", "turn_deadzone")) {
        inspect.add<XrThumbstickLocomotionComponent, double>(
            "XrThumbstickLocomotionComponent",
            &XrThumbstickLocomotionComponent::turn_deadzone,
            "turn_deadzone",
            "Turn Deadzone",
            "double"
        );
    }
}

void XrThumbstickLocomotionComponent::update(float dt) {
    if (!entity().valid()) {
        return;
    }
    if (!entity().get_component<XrOriginComponent>()) {
        tc_log(
            TC_LOG_ERROR,
            "[XrThumbstickLocomotionComponent] entity '%s' has no XrOriginComponent",
            entity().name()
        );
        return;
    }

    xr::XrRigInputState* input = xr::XrInput::get_state(input_device_id);
    if (!input) {
        if (!_logged_missing_input) {
            tc_log(
                TC_LOG_ERROR,
                "[XrThumbstickLocomotionComponent] XR input device '%s' is not registered",
                input_device_id.c_str()
            );
            _logged_missing_input = true;
        }
        return;
    }
    _logged_missing_input = false;

    if (continuous_turn_enabled) {
        _apply_turn(*input, static_cast<double>(dt));
    }

    Vec2 stick;
    if (!_read_thumbstick(*input, move_hand, stick)) {
        return;
    }
    stick = _apply_deadzone(stick, deadzone);
    if (stick.norm_squared() < 1e-8) {
        return;
    }
    _apply_move(*input, stick, static_cast<double>(dt));
}

std::string XrThumbstickLocomotionComponent::get_move_hand_str() const {
    return xr::xr_hand_to_string(move_hand);
}

void XrThumbstickLocomotionComponent::set_move_hand_str(const std::string& value) {
    move_hand = xr::xr_hand_from_string(value);
}

std::string XrThumbstickLocomotionComponent::get_turn_hand_str() const {
    return xr::xr_hand_to_string(turn_hand);
}

void XrThumbstickLocomotionComponent::set_turn_hand_str(const std::string& value) {
    turn_hand = xr::xr_hand_from_string(value);
}

std::string XrThumbstickLocomotionComponent::get_move_frame_str() const {
    return xr_locomotion_frame_to_string(move_frame);
}

void XrThumbstickLocomotionComponent::set_move_frame_str(const std::string& value) {
    move_frame = xr_locomotion_frame_from_string(value);
}

bool XrThumbstickLocomotionComponent::_read_thumbstick(
    const xr::XrRigInputState& input,
    xr::XrHand hand_value,
    Vec2& out
) const {
    const xr::XrAxis2State& state = input.hand(hand_value).thumbstick;
    if (!state.active) {
        out = Vec2::zero();
        return false;
    }

    out = state.value;
    if (invert_x) {
        out.x = -out.x;
    }
    if (invert_y) {
        out.y = -out.y;
    }
    return true;
}

Vec2 XrThumbstickLocomotionComponent::_apply_deadzone(Vec2 value, double zone) const {
    const double clamped_zone = std::clamp(zone, 0.0, 0.99);
    const double len = value.norm();
    if (len <= clamped_zone) {
        return Vec2::zero();
    }

    if (normalize_diagonal && len > 1.0) {
        value = value / len;
    }
    if (!scale_after_deadzone) {
        return value;
    }

    const double scaled = std::clamp((len - clamped_zone) / (1.0 - clamped_zone), 0.0, 1.0);
    return value.normalized() * scaled;
}

void XrThumbstickLocomotionComponent::_apply_move(
    const xr::XrRigInputState& input,
    const Vec2& stick,
    double dt
) {
    GeneralPose3 pose = entity().transform().global_pose();
    const Quat origin_rot = pose.ang;

    Vec3 right{1.0, 0.0, 0.0};
    Vec3 forward{0.0, 1.0, 0.0};

    if (move_frame == XrLocomotionFrame::HeadYaw && input.head_axes_active) {
        right = origin_rot.rotate(input.head_right_in_origin);
        forward = origin_rot.rotate(input.head_forward_in_origin);
    } else {
        right = origin_rot.rotate(Vec3{1.0, 0.0, 0.0});
        forward = origin_rot.rotate(Vec3{0.0, 1.0, 0.0});
    }

    right = projected_normalized(right, Vec3{1.0, 0.0, 0.0});
    forward = projected_normalized(forward, Vec3{0.0, 1.0, 0.0});

    Vec3 delta = (right * stick.x + forward * stick.y) * (move_speed * speed_multiplier * dt);
    pose.lin = pose.lin + delta;
    entity().transform().relocate_global(pose);
}

void XrThumbstickLocomotionComponent::_apply_turn(const xr::XrRigInputState& input, double dt) {
    Vec2 stick;
    if (!_read_thumbstick(input, turn_hand, stick)) {
        return;
    }
    if (std::abs(stick.x) <= std::clamp(turn_deadzone, 0.0, 0.99)) {
        return;
    }

    GeneralPose3 pose = entity().transform().global_pose();
    const double yaw = stick.x * turn_speed_degrees * kPi / 180.0 * dt;
    pose.ang = Quat::from_axis_angle(Vec3{0.0, 0.0, 1.0}, yaw) * pose.ang;
    entity().transform().relocate_global(pose);
}

const char* xr_locomotion_frame_to_string(XrLocomotionFrame frame) {
    switch (frame) {
        case XrLocomotionFrame::Origin:
            return "origin";
        case XrLocomotionFrame::HeadYaw:
            return "head_yaw";
    }
    return "head_yaw";
}

XrLocomotionFrame xr_locomotion_frame_from_string(const std::string& value) {
    if (value == "origin") {
        return XrLocomotionFrame::Origin;
    }
    return XrLocomotionFrame::HeadYaw;
}

REGISTER_COMPONENT(XrThumbstickLocomotionComponent, CxxComponent);
REQUIRE_COMPONENT(XrThumbstickLocomotionComponent, XrOriginComponent);

static struct _XrThumbstickLocomotionChoiceFieldsRegistrar {
    _XrThumbstickLocomotionChoiceFieldsRegistrar() {
        {
            tc::InspectFieldInfo info;
            info.type_name = "XrThumbstickLocomotionComponent";
            info.path = "move_hand";
            info.label = "Move Hand";
            info.kind = "string";
            info.choices.push_back({"left", "Left"});
            info.choices.push_back({"right", "Right"});
            info.getter = [](void* obj) -> tc_value {
                auto* c = static_cast<XrThumbstickLocomotionComponent*>(obj);
                return tc_value_string(c->get_move_hand_str().c_str());
            };
            info.setter = [](void* obj, tc_value value, void*) {
                auto* c = static_cast<XrThumbstickLocomotionComponent*>(obj);
                if (value.type == TC_VALUE_STRING && value.data.s) {
                    c->set_move_hand_str(value.data.s);
                }
            };
            tc::InspectRegistry::instance().add_field_with_choices(
                "XrThumbstickLocomotionComponent",
                std::move(info)
            );
        }
        {
            tc::InspectFieldInfo info;
            info.type_name = "XrThumbstickLocomotionComponent";
            info.path = "turn_hand";
            info.label = "Turn Hand";
            info.kind = "string";
            info.choices.push_back({"left", "Left"});
            info.choices.push_back({"right", "Right"});
            info.getter = [](void* obj) -> tc_value {
                auto* c = static_cast<XrThumbstickLocomotionComponent*>(obj);
                return tc_value_string(c->get_turn_hand_str().c_str());
            };
            info.setter = [](void* obj, tc_value value, void*) {
                auto* c = static_cast<XrThumbstickLocomotionComponent*>(obj);
                if (value.type == TC_VALUE_STRING && value.data.s) {
                    c->set_turn_hand_str(value.data.s);
                }
            };
            tc::InspectRegistry::instance().add_field_with_choices(
                "XrThumbstickLocomotionComponent",
                std::move(info)
            );
        }
        {
            tc::InspectFieldInfo info;
            info.type_name = "XrThumbstickLocomotionComponent";
            info.path = "move_frame";
            info.label = "Move Frame";
            info.kind = "string";
            info.choices.push_back({"head_yaw", "Head Yaw"});
            info.choices.push_back({"origin", "Origin"});
            info.getter = [](void* obj) -> tc_value {
                auto* c = static_cast<XrThumbstickLocomotionComponent*>(obj);
                return tc_value_string(c->get_move_frame_str().c_str());
            };
            info.setter = [](void* obj, tc_value value, void*) {
                auto* c = static_cast<XrThumbstickLocomotionComponent*>(obj);
                if (value.type == TC_VALUE_STRING && value.data.s) {
                    c->set_move_frame_str(value.data.s);
                }
            };
            tc::InspectRegistry::instance().add_field_with_choices(
                "XrThumbstickLocomotionComponent",
                std::move(info)
            );
        }
    }
} _xr_thumbstick_locomotion_choice_fields_registrar;

} // namespace termin
