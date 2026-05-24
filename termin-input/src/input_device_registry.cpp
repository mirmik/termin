#include <termin/input/input_device_registry.hpp>

#include <mutex>
#include <unordered_map>

#include <tcbase/tc_log.h>

namespace termin::input {

namespace {

std::mutex g_registry_mutex;
std::unordered_map<std::string, InputDeviceRecord> g_devices;

} // namespace

InputDeviceRegistry& InputDeviceRegistry::instance() {
    static InputDeviceRegistry registry;
    return registry;
}

void InputDeviceRegistry::register_device(
    const std::string& id,
    InputDeviceKind kind,
    void* state
) {
    if (id.empty()) {
        tc_log(TC_LOG_ERROR, "[InputDeviceRegistry] cannot register device with empty id");
        return;
    }
    if (!state) {
        tc_log(TC_LOG_ERROR, "[InputDeviceRegistry] cannot register device '%s' with NULL state", id.c_str());
        return;
    }

    std::lock_guard<std::mutex> lock(g_registry_mutex);
    InputDeviceRecord record;
    record.id = id;
    record.kind = kind;
    record.state = state;
    record.connected = true;
    g_devices[id] = record;
}

void InputDeviceRegistry::unregister_device(const std::string& id) {
    if (id.empty()) {
        tc_log(TC_LOG_ERROR, "[InputDeviceRegistry] cannot unregister device with empty id");
        return;
    }

    std::lock_guard<std::mutex> lock(g_registry_mutex);
    g_devices.erase(id);
}

void InputDeviceRegistry::update_frame_index(const std::string& id, uint64_t frame_index) {
    if (id.empty()) {
        tc_log(TC_LOG_ERROR, "[InputDeviceRegistry] cannot update frame index for empty device id");
        return;
    }

    std::lock_guard<std::mutex> lock(g_registry_mutex);
    auto it = g_devices.find(id);
    if (it == g_devices.end()) {
        tc_log(TC_LOG_ERROR, "[InputDeviceRegistry] device '%s' is not registered", id.c_str());
        return;
    }
    it->second.frame_index = frame_index;
}

InputDeviceRecord InputDeviceRegistry::find(const std::string& id) const {
    if (id.empty()) {
        tc_log(TC_LOG_ERROR, "[InputDeviceRegistry] cannot find device with empty id");
        return {};
    }

    std::lock_guard<std::mutex> lock(g_registry_mutex);
    auto it = g_devices.find(id);
    if (it == g_devices.end()) {
        return {};
    }
    return it->second;
}

InputDeviceRecord InputDeviceRegistry::find_single(InputDeviceKind kind) const {
    std::lock_guard<std::mutex> lock(g_registry_mutex);

    InputDeviceRecord result;
    size_t count = 0;
    for (const auto& entry : g_devices) {
        const InputDeviceRecord& record = entry.second;
        if (kind != InputDeviceKind::Unknown && record.kind != kind) {
            continue;
        }
        result = record;
        ++count;
    }

    if (count == 0) {
        return {};
    }
    if (count > 1) {
        tc_log(
            TC_LOG_ERROR,
            "[InputDeviceRegistry] expected one device of kind '%s', found %zu",
            input_device_kind_to_string(kind),
            count
        );
        return {};
    }
    return result;
}

std::vector<InputDeviceRecord> InputDeviceRegistry::list(InputDeviceKind kind) const {
    std::lock_guard<std::mutex> lock(g_registry_mutex);

    std::vector<InputDeviceRecord> result;
    result.reserve(g_devices.size());
    for (const auto& entry : g_devices) {
        const InputDeviceRecord& record = entry.second;
        if (kind == InputDeviceKind::Unknown || record.kind == kind) {
            result.push_back(record);
        }
    }
    return result;
}

const char* input_device_kind_to_string(InputDeviceKind kind) {
    switch (kind) {
        case InputDeviceKind::Gamepad:
            return "gamepad";
        case InputDeviceKind::XrRig:
            return "xr_rig";
        case InputDeviceKind::Unknown:
            return "unknown";
    }
    return "unknown";
}

InputDeviceKind input_device_kind_from_string(const std::string& value) {
    if (value == "gamepad") {
        return InputDeviceKind::Gamepad;
    }
    if (value == "xr_rig") {
        return InputDeviceKind::XrRig;
    }
    return InputDeviceKind::Unknown;
}

} // namespace termin::input
