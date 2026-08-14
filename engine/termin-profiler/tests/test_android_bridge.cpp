#include "guard_main.h"

#include <chrono>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include <termin/profiler_app/android_bridge.hpp>

using namespace std::chrono_literals;
using termin::profiler_app::AndroidConnectRequest;
using termin::profiler_app::AndroidProfilerBridge;
using termin::profiler_app::ProcessResult;

namespace {
    bool wait_until(const std::function<bool()>& predicate) {
        const auto deadline = std::chrono::steady_clock::now() + 2s;
        while (std::chrono::steady_clock::now() < deadline) {
            if (predicate()) {
                return true;
            }
            std::this_thread::sleep_for(5ms);
        }
        return predicate();
    }

    struct FakeAdb {
        ProcessResult operator()(const std::vector<std::string>& arguments, std::chrono::milliseconds) {
            std::lock_guard lock(mutex);
            calls.push_back(arguments);
            if (arguments.size() >= 3 && arguments[1] == "devices") {
                return {0,
                        false,
                        "List of devices attached\n"
                        "quest-ready device product:hollywood model:Quest_3\n"
                        "quest-locked unauthorized usb:2-1\n",
                        {}};
            }
            if (!arguments.empty() && arguments.back() == "get-state") {
                return {0, false, "device\n", {}};
            }
            if (arguments.size() >= 6 && arguments[3] == "forward" && arguments[4] == "tcp:0") {
                return {0, false, "47123\n", {}};
            }
            return {0, false, {}, {}};
        }

        std::vector<std::vector<std::string>> copy_calls() const {
            std::lock_guard lock(mutex);
            return calls;
        }

        mutable std::mutex mutex;
        std::vector<std::vector<std::string>> calls;
    };
} // namespace

TEST_CASE("ADB device parser preserves ready and authorization state") {
    const auto devices =
        termin::profiler_app::parse_adb_devices("List of devices attached\n"
                                                "R1 device product:hollywood model:Quest_3 transport_id:4\n"
                                                "R2 unauthorized usb:1-2\n"
                                                "R3 offline\n");
    CHECK_EQ(devices.size(), 3U);
    CHECK_EQ(devices[0].serial, "R1");
    CHECK(devices[0].ready());
    CHECK_EQ(devices[1].state, "unauthorized");
    CHECK(!devices[1].ready());
    CHECK_EQ(devices[2].state, "offline");
}

TEST_CASE("Android profiler bridge owns launch token and exact forward") {
    auto fake = std::make_shared<FakeAdb>();
    AndroidProfilerBridge bridge([fake](const auto& arguments, auto timeout) { return (*fake)(arguments, timeout); });

    CHECK(bridge.refresh_devices("adb"));
    CHECK(wait_until([&] { return !bridge.snapshot().busy; }));
    const auto discovered = bridge.snapshot();
    CHECK_EQ(discovered.devices.size(), 2U);
    CHECK(discovered.status.find("1 ready device") != std::string::npos);

    AndroidConnectRequest request;
    request.adb_path = "adb";
    request.serial = "quest-ready";
    request.package_name = "org.example.openxr";
    request.activity_name = "android.app.NativeActivity";
    CHECK(bridge.connect(request));
    CHECK(wait_until([&] { return !bridge.snapshot().busy; }));
    CHECK(bridge.snapshot().route_active);
    CHECK_EQ(bridge.snapshot().host_port, 47123);

    auto pending = bridge.take_pending_connection();
    REQUIRE(pending.has_value());
    CHECK_EQ(pending->host_port, 47123);
    CHECK_EQ(pending->authentication_token.size(), 32U);
    CHECK(bridge.snapshot().status.find(pending->authentication_token) == std::string::npos);

    const auto calls = fake->copy_calls();
    REQUIRE(calls.size() >= 5U);
    CHECK(calls[1] == (std::vector<std::string>{"adb", "-s", "quest-ready", "get-state"}));
    CHECK(calls[2] == (std::vector<std::string>{"adb", "-s", "quest-ready", "forward", "tcp:0", "tcp:46051"}));
    CHECK(calls[3] ==
          (std::vector<std::string>{"adb", "-s", "quest-ready", "shell", "am", "force-stop", "org.example.openxr"}));
    CHECK_EQ(calls[4][0], "adb");
    CHECK_EQ(calls[4][6], "-n");
    CHECK_EQ(calls[4][7], "org.example.openxr/android.app.NativeActivity");
    CHECK_EQ(calls[4][14], "--es");
    CHECK_EQ(calls[4][15], "termin.profiler.token");
    CHECK_EQ(calls[4][16], pending->authentication_token);

    CHECK(bridge.disconnect());
    CHECK(wait_until([&] { return !bridge.snapshot().busy; }));
    CHECK(!bridge.snapshot().route_active);
    const auto disconnected_calls = fake->copy_calls();
    CHECK(disconnected_calls.back() ==
          (std::vector<std::string>{"adb", "-s", "quest-ready", "forward", "--remove", "tcp:47123"}));
}

TEST_CASE("Android profiler bridge validates components without invoking adb") {
    auto fake = std::make_shared<FakeAdb>();
    AndroidProfilerBridge bridge([fake](const auto& arguments, auto timeout) { return (*fake)(arguments, timeout); });
    AndroidConnectRequest request;
    request.adb_path = "adb";
    request.serial = "quest";
    request.package_name = "org.example;bad";
    CHECK(!bridge.connect(request));
    CHECK(fake->copy_calls().empty());
    CHECK(bridge.snapshot().status.find("Package") != std::string::npos);

    request.package_name = "org.example.good";
    request.activity_name = "android.app.NativeActivity --es injected value";
    CHECK(!bridge.connect(request));
    CHECK(fake->copy_calls().empty());
}

GUARD_TEST_MAIN();
