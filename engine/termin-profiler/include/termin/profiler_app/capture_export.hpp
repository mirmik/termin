#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

#include <termin/frame_profiler/frame_profiler_source.hpp>
#include <termin/profiler_app/android_bridge.hpp>

namespace termin::profiler_app {

    inline constexpr std::uint32_t capture_json_schema_version = 1;

    struct CaptureExportMetadata {
        std::string transport = "quest-adb";
        std::string device_serial;
        std::string package_name;
        std::string activity_name;
        std::size_t requested_frames = 0;
        std::size_t warmup_frames = 0;
        bool sections_requested = false;
        std::uint64_t gpu_tail_timeout_ms = 0;
    };

    struct CaptureSummary {
        std::size_t frame_count = 0;
        std::size_t hitch_count = 0;
        std::size_t gpu_resolved_count = 0;
        double interval_p50_ms = 0.0;
        double interval_p95_ms = 0.0;
        double interval_p99_ms = 0.0;
        double interval_max_ms = 0.0;
        double active_p50_ms = 0.0;
        double active_p95_ms = 0.0;
        double active_max_ms = 0.0;
        double gpu_p50_ms = 0.0;
        double gpu_p95_ms = 0.0;
        double gpu_max_ms = 0.0;
    };

    CaptureSummary summarize_capture(const std::vector<FrameProfilerFrame>& frames, double hitch_ratio = 1.25);
    std::string capture_to_json(const FrameProfilerSnapshot& snapshot,
                                const std::vector<FrameProfilerFrame>& frames,
                                const CaptureExportMetadata& metadata,
                                double hitch_ratio = 1.25);
    std::string devices_to_json(const std::vector<AndroidDevice>& devices);
    bool write_text_file_atomic(const std::string& path, std::string_view content, std::string& error);

} // namespace termin::profiler_app
