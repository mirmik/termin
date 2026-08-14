#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <mutex>
#include <optional>
#include <string>
#include <utility>

#include <termin/profiler_remote/client.hpp>

using namespace std::chrono_literals;
using namespace termin::profiler_remote;

namespace {

    struct ObservedState {
        std::mutex mutex;
        std::condition_variable changed;
        std::optional<TargetHello> hello;
        bool start_cadence_acknowledged = false;
        bool pause_cadence_acknowledged = false;
        bool start_detailed_acknowledged = false;
        bool pause_detailed_acknowledged = false;
        std::optional<WireFrame> cadence_frame;
        std::optional<WireFrame> detailed_frame;
        std::string error;
        std::string disconnect_detail;
    };

    bool wait_for(ObservedState& state, const auto& predicate) {
        std::unique_lock lock(state.mutex);
        return state.changed.wait_for(lock, 8s, predicate);
    }

    std::string error_text(ObservedState& state) {
        std::lock_guard lock(state.mutex);
        return state.error;
    }

    bool parse_port(const char* text, std::uint16_t& port) {
        char* end = nullptr;
        const unsigned long parsed = std::strtoul(text, &end, 10);
        if (!text[0] || !end || *end || parsed == 0 || parsed > 65535)
            return false;
        port = static_cast<std::uint16_t>(parsed);
        return true;
    }

} // namespace

int main(int argc, char** argv) {
    if (argc != 3) {
        std::cerr << "Usage: " << argv[0] << " PORT TOKEN\n";
        return 2;
    }
    std::uint16_t port = 0;
    if (!parse_port(argv[1], port) || !argv[2][0]) {
        std::cerr << "PORT must be in 1..65535 and TOKEN must be non-empty\n";
        return 2;
    }

    ObservedState observed;
    ClientConfig config;
    config.port = port;
    config.authentication_token = argv[2];
    config.reconnect = true;
    RemoteProfilerClient client(
        std::move(config),
        [&](const DecodedMessage& decoded) {
            std::lock_guard lock(observed.mutex);
            if (const auto* hello = std::get_if<TargetHello>(&decoded.message)) {
                observed.hello = *hello;
            } else if (const auto* status = std::get_if<Status>(&decoded.message)) {
                observed.start_cadence_acknowledged |=
                    status->request_id == 2 && status->capturing && !status->profiling_sections;
                observed.pause_cadence_acknowledged |= status->request_id == 3 && !status->capturing;
                observed.start_detailed_acknowledged |=
                    status->request_id == 5 && status->capturing && status->profiling_sections;
                observed.pause_detailed_acknowledged |= status->request_id == 6 && !status->capturing;
            } else if (const auto* batch = std::get_if<FrameBatch>(&decoded.message)) {
                for (const WireFrame& frame : batch->frames) {
                    if (observed.start_cadence_acknowledged && !observed.pause_cadence_acknowledged &&
                        frame.frame_number > 0 && !frame.sections_profiled && !observed.cadence_frame)
                        observed.cadence_frame = frame;
                    if (observed.start_detailed_acknowledged && !observed.pause_detailed_acknowledged &&
                        frame.sections_profiled && !frame.sections.empty() && !observed.detailed_frame)
                        observed.detailed_frame = frame;
                }
            } else if (const auto* error = std::get_if<ErrorEvent>(&decoded.message)) {
                observed.error = error->detail;
            }
            observed.changed.notify_all();
        },
        [&](std::string detail) {
            std::lock_guard lock(observed.mutex);
            observed.disconnect_detail = detail;
            if (observed.hello && !observed.pause_detailed_acknowledged && observed.error.empty())
                observed.error = detail;
            observed.changed.notify_all();
        });

    if (!client.start() || !wait_for(observed, [&] { return observed.hello.has_value() || !observed.error.empty(); })) {
        std::cerr << "Remote target handshake timed out";
        {
            std::lock_guard lock(observed.mutex);
            if (!observed.disconnect_detail.empty())
                std::cerr << ": " << observed.disconnect_detail;
        }
        std::cerr << '\n';
        client.stop();
        return 1;
    }
    if (const std::string error = error_text(observed); !error.empty()) {
        std::cerr << error << '\n';
        client.stop();
        return 1;
    }

    if (!client.send_control(Control{1, ControlKind::set_sections, false}) ||
        !client.send_control(Control{2, ControlKind::start_capture}) ||
        !wait_for(observed,
                  [&] {
                      return (observed.start_cadence_acknowledged && observed.cadence_frame.has_value()) ||
                             !observed.error.empty();
                  }) ||
        !client.send_control(Control{3, ControlKind::pause_capture}) ||
        !wait_for(observed, [&] { return observed.pause_cadence_acknowledged || !observed.error.empty(); }) ||
        !client.send_control(Control{4, ControlKind::set_sections, true}) ||
        !client.send_control(Control{5, ControlKind::start_capture}) ||
        !wait_for(observed,
                  [&] {
                      return (observed.start_detailed_acknowledged && observed.detailed_frame.has_value()) ||
                             !observed.error.empty();
                  }) ||
        !client.send_control(Control{6, ControlKind::pause_capture}) ||
        !wait_for(observed, [&] { return observed.pause_detailed_acknowledged || !observed.error.empty(); })) {
        std::cerr << "Remote capture/control smoke timed out";
        if (const std::string error = error_text(observed); !error.empty())
            std::cerr << ": " << error;
        std::cerr << '\n';
        client.stop();
        return 1;
    }

    client.stop();
    const auto& hello = *observed.hello;
    const auto& cadence = *observed.cadence_frame;
    const auto& detailed = *observed.detailed_frame;
    std::cout << "target=" << hello.platform << '/' << hello.abi << " pid=" << hello.process_id << '\n'
              << "cadence_frame=" << cadence.frame_number << " interval_ms=" << cadence.interval_ms
              << " active_ms=" << cadence.active_ms << '\n'
              << "detailed_frame=" << detailed.frame_number << " sections=" << detailed.sections.size()
              << " interval_ms=" << detailed.interval_ms << " active_ms=" << detailed.active_ms << '\n';
    return 0;
}
