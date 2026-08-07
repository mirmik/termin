#pragma once

#include <chrono>
#include <cstdint>
#include <functional>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace termin::profiler_app {

    struct ProcessResult {
        int exit_code = -1;
        bool timed_out = false;
        std::string output;
        std::string error;
    };

    using ProcessRunner =
        std::function<ProcessResult(const std::vector<std::string>& arguments, std::chrono::milliseconds timeout)>;

    struct AndroidDevice {
        std::string serial;
        std::string state;
        std::string description;

        bool ready() const {
            return state == "device";
        }
    };

    enum class AndroidBridgePhase {
        Idle,
        Refreshing,
        Ready,
        Connecting,
        Routed,
        Disconnecting,
        Error,
        Closed,
    };

    struct AndroidBridgeSnapshot {
        std::uint64_t revision = 0;
        AndroidBridgePhase phase = AndroidBridgePhase::Idle;
        std::vector<AndroidDevice> devices;
        std::string status = "Press Refresh Devices to discover an Android or Quest target.";
        bool busy = false;
        bool route_active = false;
        std::string routed_serial;
        std::uint16_t host_port = 0;
    };

    struct AndroidConnectRequest {
        std::string adb_path = "adb";
        std::string serial;
        std::string package_name;
        std::string activity_name = "android.app.NativeActivity";
        std::uint16_t device_port = 46051;
    };

    struct PendingProfilerConnection {
        std::uint16_t host_port = 0;
        std::string authentication_token;
    };

    class AndroidProfilerBridge {
    public:
        explicit AndroidProfilerBridge(ProcessRunner runner = {});
        ~AndroidProfilerBridge();

        AndroidProfilerBridge(const AndroidProfilerBridge&) = delete;
        AndroidProfilerBridge& operator=(const AndroidProfilerBridge&) = delete;

        bool refresh_devices(std::string adb_path = "adb");
        bool connect(AndroidConnectRequest request);
        bool disconnect();
        void close();

        AndroidBridgeSnapshot snapshot() const;
        std::optional<PendingProfilerConnection> take_pending_connection();

    private:
        struct Impl;
        std::unique_ptr<Impl> impl_;
    };

    std::vector<AndroidDevice> parse_adb_devices(std::string_view output);

} // namespace termin::profiler_app
