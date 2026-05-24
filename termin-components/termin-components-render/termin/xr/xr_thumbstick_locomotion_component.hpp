#pragma once

#include <string>

#include <termin/entity/component.hpp>
#include <termin/export.hpp>
#include <termin/input/xr_input.hpp>

namespace termin {

enum class XrLocomotionFrame {
    Origin,
    HeadYaw,
};

class ENTITY_API XrThumbstickLocomotionComponent : public CxxComponent {
public:
    std::string input_device_id = "xr";
    xr::XrHand move_hand = xr::XrHand::Left;
    XrLocomotionFrame move_frame = XrLocomotionFrame::HeadYaw;
    double move_speed = 1.5;
    double speed_multiplier = 1.0;
    double deadzone = 0.15;
    bool normalize_diagonal = true;
    bool scale_after_deadzone = true;
    bool invert_x = false;
    bool invert_y = false;
    bool continuous_turn_enabled = false;
    xr::XrHand turn_hand = xr::XrHand::Right;
    double turn_speed_degrees = 90.0;
    double turn_deadzone = 0.35;

private:
    bool _logged_missing_input = false;

public:
    XrThumbstickLocomotionComponent();

    static void register_type();

    void update(float dt) override;

    std::string get_move_hand_str() const;
    void set_move_hand_str(const std::string& value);
    std::string get_turn_hand_str() const;
    void set_turn_hand_str(const std::string& value);
    std::string get_move_frame_str() const;
    void set_move_frame_str(const std::string& value);

private:
    bool _read_thumbstick(const xr::XrRigInputState& input, xr::XrHand hand, Vec2& out) const;
    Vec2 _apply_deadzone(Vec2 value, double zone) const;
    void _apply_move(const xr::XrRigInputState& input, const Vec2& stick, double dt);
    void _apply_turn(const xr::XrRigInputState& input, double dt);
};

ENTITY_API const char* xr_locomotion_frame_to_string(XrLocomotionFrame frame);
ENTITY_API XrLocomotionFrame xr_locomotion_frame_from_string(const std::string& value);

} // namespace termin
