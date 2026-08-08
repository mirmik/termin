#include "guard_main.h"

#include <cmath>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

#include <termin/profiler_app/capture_export.hpp>
#include <termin/profiler_app/cli.hpp>

using namespace termin::profiler_app;

namespace {
    CliParseResult parse(std::initializer_list<const char*> arguments) {
        const std::vector<const char*> argv(arguments);
        return parse_cli_options(static_cast<int>(argv.size()), argv.data());
    }
} // namespace

TEST_CASE("Profiler CLI parses an agent-oriented Quest capture") {
    const CliParseResult result = parse({"termin_profiler_cli",
                                         "capture",
                                         "quest",
                                         "--package",
                                         "org.termin.openxr",
                                         "--serial",
                                         "quest-1",
                                         "--frames",
                                         "42",
                                         "--warmup-frames",
                                         "12",
                                         "--sections",
                                         "--gpu-tail-timeout-ms",
                                         "750",
                                         "--output",
                                         "capture.json"});

    REQUIRE(result.options.has_value());
    CHECK(result.options->command == CliCommand::CaptureQuest);
    CHECK_EQ(result.options->package_name, "org.termin.openxr");
    CHECK_EQ(result.options->activity_name, "android.app.NativeActivity");
    CHECK_EQ(result.options->serial, "quest-1");
    CHECK_EQ(result.options->frame_count, 42U);
    CHECK_EQ(result.options->warmup_frame_count, 12U);
    CHECK(result.options->sections);
    CHECK_EQ(result.options->gpu_tail_timeout.count(), 750);
    CHECK_EQ(result.options->output_path, "capture.json");
}

TEST_CASE("Profiler CLI rejects ambiguous or unsafe capture arguments") {
    CHECK(!parse({"termin_profiler_cli", "capture", "quest"}).options.has_value());
    CHECK(!parse({"termin_profiler_cli", "capture", "quest", "--package", "p", "--frames", "0"}).options.has_value());
    CHECK(!parse({"termin_profiler_cli", "capture", "quest", "--package", "p", "--device-port", "65536"})
               .options.has_value());
    CHECK(!parse({"termin_profiler_cli", "devices", "--serial", "unexpected"}).options.has_value());
}

TEST_CASE("Profiler capture JSON distinguishes missing GPU timing and escapes data") {
    termin::FrameProfilerSnapshot snapshot;
    snapshot.identity.source_id = "android\nsource";
    snapshot.identity.session_id = "session-1";
    snapshot.identity.display_name = "Quest \"device\"";
    snapshot.status.connected = true;
    snapshot.status.detail = "capture paused";

    termin::FrameProfilerFrame first;
    first.frame_number = 10;
    first.interval_ms = 13.9;
    first.active_ms = 2.0;
    first.target_interval_ms = 13.8;
    first.sections_profiled = true;
    termin::FrameProfilerSection section;
    section.name = "Scene\\Render";
    section.cpu_ms = 1.25;
    section.call_count = 2;
    first.sections.push_back(section);

    termin::FrameProfilerFrame second;
    second.frame_number = 11;
    second.interval_ms = 28.0;
    second.active_ms = 3.0;
    second.target_interval_ms = 13.8;
    second.missed_intervals = 1;
    second.has_gpu_duration = true;
    second.gpu_duration_ms = 10.5;

    const std::vector<termin::FrameProfilerFrame> frames{first, second};
    CaptureExportMetadata metadata;
    metadata.device_serial = "quest-1";
    metadata.package_name = "org.termin.openxr";
    metadata.activity_name = "android.app.NativeActivity";
    metadata.requested_frames = frames.size();
    metadata.sections_requested = true;
    const std::string json = capture_to_json(snapshot, frames, metadata);

    CHECK(json.find("\"schema\":\"termin.profiler.capture\"") != std::string::npos);
    CHECK(json.find("android\\nsource") != std::string::npos);
    CHECK(json.find("Quest \\\"device\\\"") != std::string::npos);
    CHECK(json.find("Scene\\\\Render") != std::string::npos);
    CHECK(json.find("\"gpu_duration_ms\":null") != std::string::npos);
    CHECK(json.find("\"gpu_duration_ms\":10.5") != std::string::npos);
    CHECK(json.find("\"hitch_count\":1") != std::string::npos);
    CHECK(json.find("token") == std::string::npos);

    const CaptureSummary summary = summarize_capture(frames);
    CHECK_EQ(summary.frame_count, 2U);
    CHECK_EQ(summary.hitch_count, 1U);
    CHECK_EQ(summary.gpu_resolved_count, 1U);
    CHECK(std::abs(summary.gpu_p50_ms - 10.5) < 0.0001);

    first.has_gpu_duration = false;
    second.has_gpu_duration = false;
    const std::string no_gpu_json = capture_to_json(snapshot, {first, second}, metadata);
    CHECK(no_gpu_json.find("\"gpu_duration_ms\":{\"p50\":null,\"p95\":null,\"max\":null}") != std::string::npos);
}

TEST_CASE("Profiler device JSON is stable and machine readable") {
    AndroidDevice ready{"serial-1", "device", "Quest \"2\""};
    AndroidDevice offline{"serial-2", "offline", ""};
    const std::string json = devices_to_json({ready, offline});

    CHECK(json.find("\"schema\":\"termin.profiler.devices\"") != std::string::npos);
    CHECK(json.find("\"serial\":\"serial-1\"") != std::string::npos);
    CHECK(json.find("Quest \\\"2\\\"") != std::string::npos);
    CHECK(json.find("\"ready\":true") != std::string::npos);
    CHECK(json.find("\"ready\":false") != std::string::npos);
}

TEST_CASE("Profiler capture output is atomically replaceable") {
    const std::filesystem::path path = std::filesystem::temp_directory_path() / "termin-profiler-cli-output-test.json";
    std::error_code ignored;
    std::filesystem::remove(path, ignored);

    std::string error;
    REQUIRE(write_text_file_atomic(path.string(), "first", error));
    REQUIRE(write_text_file_atomic(path.string(), "second", error));
    std::ifstream stream(path, std::ios::binary);
    const std::string content{std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>()};
    CHECK_EQ(content, "second");
    CHECK(!std::filesystem::exists(path.string() + ".termin-profiler.tmp"));
    std::filesystem::remove(path, ignored);
}

GUARD_TEST_MAIN();
