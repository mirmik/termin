#include <termin/profiler_app/cli.hpp>

#include <algorithm>
#include <charconv>
#include <cstdio>
#include <iostream>
#include <limits>
#include <thread>
#include <vector>

#include <termin/profiler_app/capture_export.hpp>
#include <termin/profiler_app/session.hpp>

namespace termin::profiler_app {
    namespace {
        using Clock = std::chrono::steady_clock;

        struct CliInterrupted {};

        void throw_if_cancelled(const CliCancellationProbe& cancellation_probe) {
            if (cancellation_probe && cancellation_probe()) {
                throw CliInterrupted{};
            }
        }

        bool parse_unsigned(std::string_view text, std::uint64_t& value) {
            value = 0;
            const auto parsed = std::from_chars(text.data(), text.data() + text.size(), value);
            return !text.empty() && parsed.ec == std::errc{} && parsed.ptr == text.data() + text.size();
        }

        bool option_value(int argc,
                          const char* const* argv,
                          int& index,
                          std::string_view option,
                          std::string& value,
                          std::string& error) {
            if (index + 1 >= argc) {
                error = std::string(option) + " requires a value";
                return false;
            }
            value = argv[++index];
            if (value.empty()) {
                error = std::string(option) + " requires a non-empty value";
                return false;
            }
            return true;
        }

        template <typename Update, typename Predicate>
        bool wait_until(Clock::time_point deadline,
                        const CliCancellationProbe& cancellation_probe,
                        Update&& update,
                        Predicate&& predicate) {
            while (Clock::now() < deadline) {
                throw_if_cancelled(cancellation_probe);
                update();
                if (predicate()) {
                    return true;
                }
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
            throw_if_cancelled(cancellation_probe);
            update();
            return predicate();
        }

        int fail(CliExitCode code, const std::string& detail) {
            std::fprintf(stderr, "termin_profiler_cli: %s\n", detail.c_str());
            return static_cast<int>(code);
        }

        const AndroidDevice*
        select_device(const AndroidBridgeSnapshot& snapshot, const std::string& requested_serial, std::string& error) {
            if (!requested_serial.empty()) {
                const auto found = std::find_if(snapshot.devices.begin(),
                                                snapshot.devices.end(),
                                                [&](const auto& item) { return item.serial == requested_serial; });
                if (found == snapshot.devices.end()) {
                    error = "requested Android device was not discovered: " + requested_serial;
                    return nullptr;
                }
                if (!found->ready()) {
                    error = "requested Android device is not ready: " + requested_serial + " (" + found->state + ")";
                    return nullptr;
                }
                return &*found;
            }
            const AndroidDevice* selected = nullptr;
            for (const AndroidDevice& device : snapshot.devices) {
                if (!device.ready()) {
                    continue;
                }
                if (selected) {
                    error = "multiple ready Android devices found; pass --serial";
                    return nullptr;
                }
                selected = &device;
            }
            if (!selected) {
                error = "no ready Android device found";
            }
            return selected;
        }

        bool all_gpu_resolved(const FrameProfilerSnapshot& snapshot, const std::vector<std::int64_t>& frame_ids) {
            return std::all_of(frame_ids.begin(), frame_ids.end(), [&](std::int64_t frame_number) {
                const FrameProfilerFrame* frame = snapshot.find(frame_number);
                return frame && frame->has_gpu_duration;
            });
        }

        int run_devices(const CliOptions& options,
                        ProcessRunner runner,
                        const CliCancellationProbe& cancellation_probe) {
            AndroidProfilerBridge bridge(std::move(runner));
            if (!bridge.refresh_devices(options.adb_path)) {
                return fail(CliExitCode::Device, "could not start ADB device discovery");
            }
            const auto deadline = Clock::now() + options.timeout;
            if (!wait_until(deadline, cancellation_probe, [] {}, [&] { return !bridge.snapshot().busy; })) {
                return fail(CliExitCode::Device, "ADB device discovery timed out");
            }
            const AndroidBridgeSnapshot snapshot = bridge.snapshot();
            if (snapshot.phase == AndroidBridgePhase::Error) {
                return fail(CliExitCode::Device, snapshot.status);
            }
            std::cout << devices_to_json(snapshot.devices) << '\n';
            return static_cast<int>(CliExitCode::Success);
        }

        int run_capture_quest(const CliOptions& options,
                              ProcessRunner runner,
                              const CliCancellationProbe& cancellation_probe) {
            AndroidProfilerBridge bridge(std::move(runner));
            if (!bridge.refresh_devices(options.adb_path)) {
                return fail(CliExitCode::Device, "could not start ADB device discovery");
            }
            auto deadline = Clock::now() + options.timeout;
            if (!wait_until(deadline, cancellation_probe, [] {}, [&] { return !bridge.snapshot().busy; })) {
                return fail(CliExitCode::Device, "ADB device discovery timed out");
            }
            AndroidBridgeSnapshot bridge_snapshot = bridge.snapshot();
            if (bridge_snapshot.phase == AndroidBridgePhase::Error) {
                return fail(CliExitCode::Device, bridge_snapshot.status);
            }
            std::string selection_error;
            const AndroidDevice* selected = select_device(bridge_snapshot, options.serial, selection_error);
            if (!selected) {
                return fail(CliExitCode::Device, selection_error);
            }
            const std::string selected_serial = selected->serial;

            AndroidConnectRequest request;
            request.adb_path = options.adb_path;
            request.serial = selected_serial;
            request.package_name = options.package_name;
            request.activity_name = options.activity_name;
            request.device_port = options.device_port;
            std::fprintf(stderr,
                         "termin_profiler_cli: launching %s on %s\n",
                         request.package_name.c_str(),
                         selected_serial.c_str());
            if (!bridge.connect(std::move(request))) {
                return fail(CliExitCode::Device, bridge.snapshot().status);
            }
            deadline = Clock::now() + options.timeout;
            if (!wait_until(deadline, cancellation_probe, [] {}, [&] { return !bridge.snapshot().busy; })) {
                return fail(CliExitCode::Device, "Android profiler route setup timed out");
            }
            bridge_snapshot = bridge.snapshot();
            if (bridge_snapshot.phase == AndroidBridgePhase::Error) {
                return fail(CliExitCode::Device, bridge_snapshot.status);
            }
            auto pending = bridge.take_pending_connection();
            if (!pending) {
                return fail(CliExitCode::Device, "Android profiler route did not publish a connection endpoint");
            }

            const std::size_t capacity =
                std::max<std::size_t>(options.frame_count + options.warmup_frame_count + 512, 1024);
            RemoteProfilerSession session(capacity);
            if (!session.connect(std::to_string(pending->host_port), std::move(pending->authentication_token))) {
                return fail(CliExitCode::Connection, "could not start remote profiler client");
            }
            deadline = Clock::now() + options.timeout;
            if (!wait_until(
                    deadline, cancellation_probe, [&] { session.update(); }, [&] { return session.connected(); })) {
                return fail(CliExitCode::Connection,
                            "remote profiler handshake timed out: " + session.snapshot()->status.detail);
            }
            std::fprintf(
                stderr, "termin_profiler_cli: connected to %s\n", session.snapshot()->identity.display_name.c_str());

            session.profiler().set_profiling(options.sections);
            deadline = Clock::now() + options.timeout;
            if (!wait_until(
                    deadline,
                    cancellation_probe,
                    [&] { session.update(); },
                    [&] { return session.snapshot()->status.profiling_sections == options.sections; })) {
                return fail(CliExitCode::Capture, "section profiling control was not acknowledged");
            }
            const auto clear_capture = [&]() {
                session.profiler().clear();
                const auto control_deadline = Clock::now() + options.timeout;
                return wait_until(
                    control_deadline,
                    cancellation_probe,
                    [&] { session.update(); },
                    [&] {
                        const auto snapshot = session.snapshot();
                        return snapshot->frames.empty() && snapshot->status.detail == "capture cleared";
                    });
            };
            const auto start_capture = [&]() {
                session.profiler().start_capture();
                const auto control_deadline = Clock::now() + options.timeout;
                return wait_until(
                    control_deadline,
                    cancellation_probe,
                    [&] { session.update(); },
                    [&] { return session.snapshot()->status.capturing; });
            };
            const auto pause_capture = [&]() {
                session.profiler().pause();
                const auto control_deadline = Clock::now() + options.timeout;
                return wait_until(
                    control_deadline,
                    cancellation_probe,
                    [&] { session.update(); },
                    [&] { return !session.snapshot()->status.capturing; });
            };

            if (!clear_capture()) {
                return fail(CliExitCode::Capture, "clear capture control was not acknowledged");
            }
            if (options.warmup_frame_count > 0) {
                if (!start_capture()) {
                    return fail(CliExitCode::Capture, "warm-up capture control was not acknowledged");
                }
                std::fprintf(stderr, "termin_profiler_cli: warming up for %zu frames\n", options.warmup_frame_count);
                deadline = Clock::now() + options.timeout;
                if (!wait_until(
                        deadline,
                        cancellation_probe,
                        [&] { session.update(); },
                        [&] { return session.snapshot()->frames.size() >= options.warmup_frame_count; })) {
                    return fail(CliExitCode::Capture, "warm-up timed out");
                }
                if (!pause_capture()) {
                    return fail(CliExitCode::Capture, "warm-up pause control was not acknowledged");
                }
                if (!clear_capture()) {
                    return fail(CliExitCode::Capture, "post-warm-up clear control was not acknowledged");
                }
            }
            if (!start_capture()) {
                return fail(CliExitCode::Capture, "start capture control was not acknowledged");
            }
            std::fprintf(stderr, "termin_profiler_cli: capturing %zu frames\n", options.frame_count);
            deadline = Clock::now() + options.timeout;
            if (!wait_until(
                    deadline,
                    cancellation_probe,
                    [&] { session.update(); },
                    [&] { return session.snapshot()->frames.size() >= options.frame_count; })) {
                return fail(CliExitCode::Capture,
                            "capture timed out after receiving " + std::to_string(session.snapshot()->frames.size()) +
                                "/" + std::to_string(options.frame_count) + " frames");
            }

            auto captured_snapshot = session.snapshot();
            std::vector<std::int64_t> frame_ids;
            frame_ids.reserve(options.frame_count);
            for (std::size_t index = 0; index < options.frame_count; ++index) {
                frame_ids.push_back(captured_snapshot->frames[index].frame_number);
            }
            if (options.gpu_tail_timeout.count() > 0) {
                const auto gpu_deadline = Clock::now() + options.gpu_tail_timeout;
                wait_until(
                    gpu_deadline,
                    cancellation_probe,
                    [&] { session.update(); },
                    [&] { return all_gpu_resolved(*session.snapshot(), frame_ids); });
            }
            if (!pause_capture()) {
                return fail(CliExitCode::Capture, "pause capture control was not acknowledged");
            }
            captured_snapshot = session.snapshot();
            throw_if_cancelled(cancellation_probe);
            std::vector<FrameProfilerFrame> frames;
            frames.reserve(frame_ids.size());
            for (const std::int64_t frame_number : frame_ids) {
                const FrameProfilerFrame* frame = captured_snapshot->find(frame_number);
                if (!frame) {
                    return fail(CliExitCode::Capture,
                                "captured frame was evicted before export: " + std::to_string(frame_number));
                }
                frames.push_back(*frame);
            }

            CaptureExportMetadata metadata;
            metadata.device_serial = selected_serial;
            metadata.package_name = options.package_name;
            metadata.activity_name = options.activity_name;
            metadata.requested_frames = options.frame_count;
            metadata.warmup_frames = options.warmup_frame_count;
            metadata.sections_requested = options.sections;
            metadata.gpu_tail_timeout_ms = static_cast<std::uint64_t>(options.gpu_tail_timeout.count());
            const std::string json = capture_to_json(*captured_snapshot, frames, metadata);
            if (options.output_path == "-") {
                std::cout << json << '\n';
            } else {
                std::string error;
                if (!write_text_file_atomic(options.output_path, json, error)) {
                    return fail(CliExitCode::Output, error);
                }
                std::fprintf(stderr, "termin_profiler_cli: wrote %s\n", options.output_path.c_str());
            }
            const CaptureSummary summary = summarize_capture(frames);
            std::fprintf(stderr,
                         "termin_profiler_cli: complete frames=%zu hitches=%zu gpu=%zu/%zu\n",
                         summary.frame_count,
                         summary.hitch_count,
                         summary.gpu_resolved_count,
                         summary.frame_count);
            session.disconnect();
            bridge.close();
            return static_cast<int>(CliExitCode::Success);
        }
    } // namespace

    std::string cli_usage() {
        return "Usage:\n"
               "  termin_profiler_cli devices [--adb PATH] [--json]\n"
               "  termin_profiler_cli capture quest --package ID [--serial SERIAL] [--activity CLASS]\n"
               "      [--frames N] [--warmup-frames N] [--sections] [--adb PATH] [--device-port PORT]\n"
               "      [--timeout-ms N] [--gpu-tail-timeout-ms N] [--output FILE|-]\n";
    }

    CliParseResult parse_cli_options(int argc, const char* const* argv) {
        CliParseResult result;
        if (argc <= 1) {
            result.error = "missing command";
            return result;
        }
        CliOptions options;
        int first_option = 2;
        const std::string_view command(argv[1]);
        if (command == "--help" || command == "-h" || command == "help") {
            options.command = CliCommand::Help;
            result.options = std::move(options);
            return result;
        }
        if (command == "devices") {
            options.command = CliCommand::Devices;
        } else if (command == "capture") {
            if (argc <= 2 || std::string_view(argv[2]) != "quest") {
                result.error = "capture currently requires the 'quest' transport";
                return result;
            }
            options.command = CliCommand::CaptureQuest;
            first_option = 3;
        } else {
            result.error = "unknown command: " + std::string(command);
            return result;
        }

        for (int index = first_option; index < argc; ++index) {
            const std::string_view option(argv[index]);
            std::string value;
            if (option == "--json" && options.command == CliCommand::Devices) {
                continue;
            }
            if (option == "--sections" && options.command == CliCommand::CaptureQuest) {
                options.sections = true;
                continue;
            }
            if (option == "--adb") {
                if (!option_value(argc, argv, index, option, options.adb_path, result.error))
                    return result;
            } else if (option == "--serial" && options.command == CliCommand::CaptureQuest) {
                if (!option_value(argc, argv, index, option, options.serial, result.error))
                    return result;
            } else if (option == "--package" && options.command == CliCommand::CaptureQuest) {
                if (!option_value(argc, argv, index, option, options.package_name, result.error))
                    return result;
            } else if (option == "--activity" && options.command == CliCommand::CaptureQuest) {
                if (!option_value(argc, argv, index, option, options.activity_name, result.error))
                    return result;
            } else if (option == "--output" && options.command == CliCommand::CaptureQuest) {
                if (!option_value(argc, argv, index, option, options.output_path, result.error))
                    return result;
            } else if (options.command == CliCommand::CaptureQuest &&
                       (option == "--frames" || option == "--warmup-frames" || option == "--device-port" ||
                        option == "--timeout-ms" || option == "--gpu-tail-timeout-ms")) {
                if (!option_value(argc, argv, index, option, value, result.error))
                    return result;
                std::uint64_t parsed = 0;
                if (!parse_unsigned(value, parsed)) {
                    result.error = std::string(option) + " requires an unsigned integer";
                    return result;
                }
                if (option == "--frames") {
                    if (parsed == 0 || parsed > 100000) {
                        result.error = "--frames must be in 1..100000";
                        return result;
                    }
                    options.frame_count = static_cast<std::size_t>(parsed);
                } else if (option == "--warmup-frames") {
                    if (parsed > 100000) {
                        result.error = "--warmup-frames must be in 0..100000";
                        return result;
                    }
                    options.warmup_frame_count = static_cast<std::size_t>(parsed);
                } else if (option == "--device-port") {
                    if (parsed == 0 || parsed > 65535) {
                        result.error = "--device-port must be in 1..65535";
                        return result;
                    }
                    options.device_port = static_cast<std::uint16_t>(parsed);
                } else if (option == "--timeout-ms") {
                    if (parsed == 0 || parsed > 3600000) {
                        result.error = "--timeout-ms must be in 1..3600000";
                        return result;
                    }
                    options.timeout = std::chrono::milliseconds(parsed);
                } else {
                    if (parsed > 3600000) {
                        result.error = "--gpu-tail-timeout-ms must be in 0..3600000";
                        return result;
                    }
                    options.gpu_tail_timeout = std::chrono::milliseconds(parsed);
                }
            } else {
                result.error = "unknown option: " + std::string(option);
                return result;
            }
        }
        if (options.command == CliCommand::CaptureQuest && options.package_name.empty()) {
            result.error = "capture quest requires --package ID";
            return result;
        }
        result.options = std::move(options);
        return result;
    }

    int run_cli(const CliOptions& options, ProcessRunner runner, CliCancellationProbe cancellation_probe) {
        try {
            switch (options.command) {
            case CliCommand::Help:
                std::cout << cli_usage();
                return static_cast<int>(CliExitCode::Success);
            case CliCommand::Devices:
                return run_devices(options, std::move(runner), cancellation_probe);
            case CliCommand::CaptureQuest:
                return run_capture_quest(options, std::move(runner), cancellation_probe);
            }
        } catch (const CliInterrupted&) {
            return fail(CliExitCode::Interrupted, "interrupted; owned resources were closed");
        }
        return fail(CliExitCode::Runtime, "invalid command state");
    }

} // namespace termin::profiler_app
