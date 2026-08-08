#pragma once

#include <chrono>
#include <cstddef>
#include <optional>
#include <string>

#include <termin/profiler_app/android_bridge.hpp>

namespace termin::profiler_app {

    enum class CliCommand {
        Help,
        Devices,
        CaptureQuest,
    };

    struct CliOptions {
        CliCommand command = CliCommand::Help;
        std::string adb_path;
        std::string serial;
        std::string package_name;
        std::string activity_name = "android.app.NativeActivity";
        std::string output_path = "-";
        std::size_t frame_count = 300;
        std::size_t warmup_frame_count = 30;
        std::uint16_t device_port = 46051;
        bool sections = false;
        std::chrono::milliseconds timeout{15000};
        std::chrono::milliseconds gpu_tail_timeout{2000};
    };

    struct CliParseResult {
        std::optional<CliOptions> options;
        std::string error;
    };

    enum class CliExitCode : int {
        Success = 0,
        Runtime = 1,
        Usage = 2,
        Device = 3,
        Connection = 4,
        Capture = 5,
        Output = 6,
    };

    CliParseResult parse_cli_options(int argc, const char* const* argv);
    std::string cli_usage();
    int run_cli(const CliOptions& options, ProcessRunner runner = {});

} // namespace termin::profiler_app
