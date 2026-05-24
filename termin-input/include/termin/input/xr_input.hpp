#pragma once

#include <cstdint>
#include <string>

#include <termin/geom/pose3.hpp>
#include <termin/geom/vec2.hpp>
#include <termin/geom/vec3.hpp>
#include <termin_input/export.hpp>

namespace termin::xr {

enum class XrHand {
    Left,
    Right,
};

struct XrAxis2State {
    Vec2 value{0.0, 0.0};
    bool active = false;
    bool changed_since_last_sync = false;
};

struct XrPoseState {
    Pose3 pose{};
    bool active = false;
};

struct XrHandInputState {
    XrAxis2State thumbstick;
    XrPoseState aim_pose;
    XrPoseState grip_pose;
};

struct XrRigInputState {
    std::string id = "xr";
    uint64_t frame_index = 0;
    XrHandInputState left;
    XrHandInputState right;
    XrPoseState head_pose;
    Vec3 head_forward_in_origin{0.0, 1.0, 0.0};
    Vec3 head_right_in_origin{1.0, 0.0, 0.0};
    bool head_axes_active = false;

    const XrHandInputState& hand(XrHand hand) const;
    XrHandInputState& hand(XrHand hand);
};

class TERMIN_INPUT_API XrInput {
public:
    static void register_state(const std::string& id, XrRigInputState* state);
    static void unregister_state(const std::string& id);
    static XrRigInputState* get_state(const std::string& id);
    static XrRigInputState* current();
};

TERMIN_INPUT_API const char* xr_hand_to_string(XrHand hand);
TERMIN_INPUT_API XrHand xr_hand_from_string(const std::string& value);

} // namespace termin::xr
