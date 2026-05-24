#include <termin/input/xr_input.hpp>

#include <tcbase/tc_log.h>
#include <termin/input/input_device_registry.hpp>

namespace termin::xr {

const XrHandInputState& XrRigInputState::hand(XrHand hand_value) const {
    switch (hand_value) {
        case XrHand::Right:
            return right;
        case XrHand::Left:
            return left;
    }
    return left;
}

XrHandInputState& XrRigInputState::hand(XrHand hand_value) {
    switch (hand_value) {
        case XrHand::Right:
            return right;
        case XrHand::Left:
            return left;
    }
    return left;
}

void XrInput::register_state(const std::string& id, XrRigInputState* state) {
    if (!state) {
        tc_log(TC_LOG_ERROR, "[XrInput] cannot register '%s': state is NULL", id.c_str());
        return;
    }
    state->id = id;
    termin::input::InputDeviceRegistry::instance().register_device(
        id,
        termin::input::InputDeviceKind::XrRig,
        state
    );
}

void XrInput::unregister_state(const std::string& id) {
    termin::input::InputDeviceRegistry::instance().unregister_device(id);
}

XrRigInputState* XrInput::get_state(const std::string& id) {
    termin::input::InputDeviceRecord record =
        termin::input::InputDeviceRegistry::instance().find(id);
    if (!record.connected || record.kind != termin::input::InputDeviceKind::XrRig) {
        return nullptr;
    }
    return static_cast<XrRigInputState*>(record.state);
}

XrRigInputState* XrInput::current() {
    termin::input::InputDeviceRecord record =
        termin::input::InputDeviceRegistry::instance().find_single(
            termin::input::InputDeviceKind::XrRig
        );
    if (!record.connected) {
        return nullptr;
    }
    return static_cast<XrRigInputState*>(record.state);
}

const char* xr_hand_to_string(XrHand hand) {
    switch (hand) {
        case XrHand::Right:
            return "right";
        case XrHand::Left:
            return "left";
    }
    return "left";
}

XrHand xr_hand_from_string(const std::string& value) {
    if (value == "right") {
        return XrHand::Right;
    }
    return XrHand::Left;
}

} // namespace termin::xr
