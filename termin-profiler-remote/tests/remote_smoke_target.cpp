#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <string>
#include <thread>

#ifdef _WIN32
#include <process.h>
#else
#include <unistd.h>
#endif

#include <tc_profiler.h>
#include <termin/profiler_remote/target_service.hpp>

using namespace std::chrono_literals;
using namespace termin::profiler_remote;

namespace {

    bool parse_port(const char* text, std::uint16_t& port) {
        char* end = nullptr;
        const unsigned long parsed = std::strtoul(text, &end, 10);
        if (!text[0] || !end || *end || parsed == 0 || parsed > 65535)
            return false;
        port = static_cast<std::uint16_t>(parsed);
        return true;
    }

    double monotonic_ms() {
        return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now().time_since_epoch()).count();
    }

    std::uint32_t process_id() {
#ifdef _WIN32
        return static_cast<std::uint32_t>(_getpid());
#else
        return static_cast<std::uint32_t>(getpid());
#endif
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

    TargetServiceConfig config;
    config.port = port;
    config.authentication_token = argv[2];
    config.platform = "desktop-smoke";
    config.abi = "host";
    config.build_type = "test";
    config.process_id = process_id();
    RemoteProfilerTarget target(std::move(config));
    if (!target.start()) {
        std::cerr << "Failed to start remote profiler target\n";
        return 1;
    }

    std::cout << "READY port=" << target.status().listening_port << '\n' << std::flush;

    const auto deadline = std::chrono::steady_clock::now() + 30s;
    double previous_start_ms = 0.0;
    bool saw_detailed_capture = false;
    bool capture_sequence_complete = false;
    while (std::chrono::steady_clock::now() < deadline) {
        target.pump_frame_thread();
        const TargetServiceStatus status = target.status();
        saw_detailed_capture |= status.capturing && status.profiling_sections;
        capture_sequence_complete |= saw_detailed_capture && !status.capturing;
        if (capture_sequence_complete && !status.client_connected) {
            std::cout << "COMPLETE frames=" << status.completed_frames << " bytes=" << status.transmitted_bytes << '\n';
            target.stop();
            return status.completed_frames > 0 && status.transmitted_bytes > 0 ? 0 : 1;
        }

        if (tc_profiler_frame_capture_enabled()) {
            const double start_ms = monotonic_ms();
            const tc_profiler_frame_info info{
                start_ms,
                previous_start_ms > 0.0 ? start_ms - previous_start_ms : 0.0,
                16.6666667,
                0.0,
                0,
            };
            previous_start_ms = start_ms;
            tc_profiler_begin_frame_with_info(&info);
            if (tc_profiler_enabled())
                tc_profiler_begin_section("Remote smoke workload");
            std::this_thread::sleep_for(1ms);
            if (tc_profiler_enabled())
                tc_profiler_end_section();
            tc_profiler_end_frame();
            target.pump_frame_thread();
        }
        std::this_thread::sleep_for(15ms);
    }

    const TargetServiceStatus status = target.status();
    std::cerr << "Remote profiler target timed out: connected=" << status.client_connected
              << " capturing=" << status.capturing << " detailed=" << status.profiling_sections
              << " frames=" << status.completed_frames << '\n';
    target.stop();
    return 1;
}
