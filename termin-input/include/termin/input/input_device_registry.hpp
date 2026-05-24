#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include <termin_input/export.hpp>

namespace termin::input {

using InputDeviceId = std::string;

enum class InputDeviceKind {
    Unknown,
    Gamepad,
    XrRig,
};

struct InputDeviceRecord {
    InputDeviceId id;
    InputDeviceKind kind = InputDeviceKind::Unknown;
    void* state = nullptr;
    uint64_t frame_index = 0;
    bool connected = false;
};

class TERMIN_INPUT_API InputDeviceRegistry {
public:
    static InputDeviceRegistry& instance();

    void register_device(
        const std::string& id,
        InputDeviceKind kind,
        void* state
    );
    void unregister_device(const std::string& id);
    void update_frame_index(const std::string& id, uint64_t frame_index);

    InputDeviceRecord find(const std::string& id) const;
    InputDeviceRecord find_single(InputDeviceKind kind) const;
    std::vector<InputDeviceRecord> list(InputDeviceKind kind = InputDeviceKind::Unknown) const;

private:
    InputDeviceRegistry() = default;
};

TERMIN_INPUT_API const char* input_device_kind_to_string(InputDeviceKind kind);
TERMIN_INPUT_API InputDeviceKind input_device_kind_from_string(const std::string& value);

} // namespace termin::input
