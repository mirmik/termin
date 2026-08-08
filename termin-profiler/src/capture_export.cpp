#include <termin/profiler_app/capture_export.hpp>

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <limits>
#include <sstream>
#include <system_error>

#if defined(_WIN32)
#define NOMINMAX
#include <windows.h>
#else
#include <cerrno>
#include <cstdio>
#include <cstring>
#endif

namespace termin::profiler_app {
    namespace {
        std::string escaped_json(std::string_view value) {
            std::ostringstream out;
            out << '"';
            for (const unsigned char character : value) {
                switch (character) {
                case '"':
                    out << "\\\"";
                    break;
                case '\\':
                    out << "\\\\";
                    break;
                case '\b':
                    out << "\\b";
                    break;
                case '\f':
                    out << "\\f";
                    break;
                case '\n':
                    out << "\\n";
                    break;
                case '\r':
                    out << "\\r";
                    break;
                case '\t':
                    out << "\\t";
                    break;
                default:
                    if (character < 0x20U) {
                        out << "\\u00" << std::hex << std::setw(2) << std::setfill('0')
                            << static_cast<unsigned int>(character) << std::dec << std::setfill(' ');
                    } else {
                        out << static_cast<char>(character);
                    }
                    break;
                }
            }
            out << '"';
            return out.str();
        }

        double percentile(std::vector<double> values, double quantile) {
            if (values.empty()) {
                return 0.0;
            }
            std::sort(values.begin(), values.end());
            const double position = static_cast<double>(values.size() - 1) * quantile;
            const auto lower = static_cast<std::size_t>(position);
            const auto upper = std::min(lower + 1, values.size() - 1);
            const double fraction = position - static_cast<double>(lower);
            return values[lower] * (1.0 - fraction) + values[upper] * fraction;
        }

        double maximum(const std::vector<double>& values) {
            return values.empty() ? 0.0 : *std::max_element(values.begin(), values.end());
        }

        bool is_hitch(const FrameProfilerFrame& frame, double hitch_ratio) {
            return frame.missed_intervals > 0 ||
                   (frame.target_interval_ms > 0.0 && frame.interval_ms > frame.target_interval_ms * hitch_ratio);
        }

        const char* gap_kind_name(FrameProfilerGapKind kind) {
            switch (kind) {
            case FrameProfilerGapKind::CaptureOverwrite:
                return "capture_overwrite";
            case FrameProfilerGapKind::Source:
                return "source";
            case FrameProfilerGapKind::TransportDrop:
                return "transport_drop";
            case FrameProfilerGapKind::Disconnect:
                return "disconnect";
            }
            return "unknown";
        }

        void number(std::ostream& out, double value) {
            if (!std::isfinite(value)) {
                out << "null";
                return;
            }
            out << std::setprecision(std::numeric_limits<double>::max_digits10) << value;
        }

        void summary_json(std::ostream& out, const CaptureSummary& summary) {
            out << "{\"frame_count\":" << summary.frame_count << ",\"hitch_count\":" << summary.hitch_count
                << ",\"gpu_resolved_count\":" << summary.gpu_resolved_count << ",\"interval_ms\":{";
            out << "\"p50\":";
            number(out, summary.interval_p50_ms);
            out << ",\"p95\":";
            number(out, summary.interval_p95_ms);
            out << ",\"p99\":";
            number(out, summary.interval_p99_ms);
            out << ",\"max\":";
            number(out, summary.interval_max_ms);
            out << "},\"active_ms\":{\"p50\":";
            number(out, summary.active_p50_ms);
            out << ",\"p95\":";
            number(out, summary.active_p95_ms);
            out << ",\"max\":";
            number(out, summary.active_max_ms);
            out << "},\"gpu_duration_ms\":{\"p50\":";
            if (summary.gpu_resolved_count == 0) {
                out << "null";
            } else {
                number(out, summary.gpu_p50_ms);
            }
            out << ",\"p95\":";
            if (summary.gpu_resolved_count == 0) {
                out << "null";
            } else {
                number(out, summary.gpu_p95_ms);
            }
            out << ",\"max\":";
            if (summary.gpu_resolved_count == 0) {
                out << "null";
            } else {
                number(out, summary.gpu_max_ms);
            }
            out << "}}";
        }

        bool replace_file(const std::filesystem::path& temporary,
                          const std::filesystem::path& destination,
                          std::string& error) {
#if defined(_WIN32)
            if (MoveFileExW(
                    temporary.c_str(), destination.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) == 0) {
                error = "cannot replace output file (Windows error " + std::to_string(GetLastError()) + ")";
                return false;
            }
            return true;
#else
            if (std::rename(temporary.c_str(), destination.c_str()) != 0) {
                error = "cannot replace output file: " + std::string(std::strerror(errno));
                return false;
            }
            return true;
#endif
        }
    } // namespace

    CaptureSummary summarize_capture(const std::vector<FrameProfilerFrame>& frames, double hitch_ratio) {
        CaptureSummary summary;
        summary.frame_count = frames.size();
        std::vector<double> intervals;
        std::vector<double> active;
        std::vector<double> gpu;
        intervals.reserve(frames.size());
        active.reserve(frames.size());
        gpu.reserve(frames.size());
        for (const FrameProfilerFrame& frame : frames) {
            intervals.push_back(frame.interval_ms);
            active.push_back(frame.active_ms);
            summary.hitch_count += is_hitch(frame, hitch_ratio) ? 1U : 0U;
            if (frame.has_gpu_duration) {
                gpu.push_back(frame.gpu_duration_ms);
            }
        }
        summary.gpu_resolved_count = gpu.size();
        summary.interval_p50_ms = percentile(intervals, 0.50);
        summary.interval_p95_ms = percentile(intervals, 0.95);
        summary.interval_p99_ms = percentile(intervals, 0.99);
        summary.interval_max_ms = maximum(intervals);
        summary.active_p50_ms = percentile(active, 0.50);
        summary.active_p95_ms = percentile(active, 0.95);
        summary.active_max_ms = maximum(active);
        summary.gpu_p50_ms = percentile(gpu, 0.50);
        summary.gpu_p95_ms = percentile(gpu, 0.95);
        summary.gpu_max_ms = maximum(gpu);
        return summary;
    }

    std::string capture_to_json(const FrameProfilerSnapshot& snapshot,
                                const std::vector<FrameProfilerFrame>& frames,
                                const CaptureExportMetadata& metadata,
                                double hitch_ratio) {
        std::ostringstream out;
        out << "{\"schema\":\"termin.profiler.capture\",\"schema_version\":" << capture_json_schema_version;
        out << ",\"request\":{\"transport\":" << escaped_json(metadata.transport)
            << ",\"device_serial\":" << escaped_json(metadata.device_serial)
            << ",\"package\":" << escaped_json(metadata.package_name)
            << ",\"activity\":" << escaped_json(metadata.activity_name)
            << ",\"requested_frames\":" << metadata.requested_frames << ",\"warmup_frames\":" << metadata.warmup_frames
            << ",\"sections_requested\":" << (metadata.sections_requested ? "true" : "false")
            << ",\"gpu_tail_timeout_ms\":" << metadata.gpu_tail_timeout_ms << '}';
        out << ",\"target\":{\"source_id\":" << escaped_json(snapshot.identity.source_id)
            << ",\"session_id\":" << escaped_json(snapshot.identity.session_id)
            << ",\"display_name\":" << escaped_json(snapshot.identity.display_name) << '}';
        out << ",\"status\":{\"connected\":" << (snapshot.status.connected ? "true" : "false")
            << ",\"capturing\":" << (snapshot.status.capturing ? "true" : "false")
            << ",\"profiling_sections\":" << (snapshot.status.profiling_sections ? "true" : "false")
            << ",\"overwritten_frames\":" << snapshot.status.overwritten_frames
            << ",\"dropped_frames\":" << snapshot.status.dropped_frames
            << ",\"detail\":" << escaped_json(snapshot.status.detail) << '}';
        out << ",\"summary\":";
        summary_json(out, summarize_capture(frames, hitch_ratio));
        out << ",\"frames\":[";
        for (std::size_t frame_index = 0; frame_index < frames.size(); ++frame_index) {
            if (frame_index != 0) {
                out << ',';
            }
            const FrameProfilerFrame& frame = frames[frame_index];
            out << "{\"frame_number\":" << frame.frame_number << ",\"start_time_ms\":";
            number(out, frame.start_time_ms);
            out << ",\"interval_ms\":";
            number(out, frame.interval_ms);
            out << ",\"active_ms\":";
            number(out, frame.active_ms);
            out << ",\"target_interval_ms\":";
            number(out, frame.target_interval_ms);
            out << ",\"deadline_lateness_ms\":";
            number(out, frame.deadline_lateness_ms);
            out << ",\"missed_intervals\":" << frame.missed_intervals
                << ",\"hitch\":" << (is_hitch(frame, hitch_ratio) ? "true" : "false")
                << ",\"gap_before\":" << (frame.gap_before ? "true" : "false")
                << ",\"sections_profiled\":" << (frame.sections_profiled ? "true" : "false") << ",\"gpu_duration_ms\":";
            if (frame.has_gpu_duration) {
                number(out, frame.gpu_duration_ms);
            } else {
                out << "null";
            }
            out << ",\"sections\":[";
            for (std::size_t section_index = 0; section_index < frame.sections.size(); ++section_index) {
                if (section_index != 0) {
                    out << ',';
                }
                const FrameProfilerSection& section = frame.sections[section_index];
                out << "{\"name\":" << escaped_json(section.name) << ",\"cpu_ms\":";
                number(out, section.cpu_ms);
                out << ",\"children_ms\":";
                number(out, section.children_ms);
                out << ",\"call_count\":" << section.call_count << ",\"parent_index\":" << section.parent_index
                    << ",\"first_child\":" << section.first_child << ",\"next_sibling\":" << section.next_sibling
                    << '}';
            }
            out << "]}";
        }
        out << "],\"gaps\":[";
        for (std::size_t index = 0; index < snapshot.gaps.size(); ++index) {
            if (index != 0) {
                out << ',';
            }
            const FrameProfilerGap& gap = snapshot.gaps[index];
            out << "{\"kind\":" << escaped_json(gap_kind_name(gap.kind))
                << ",\"first_missing_frame\":" << gap.first_missing_frame
                << ",\"last_missing_frame\":" << gap.last_missing_frame << ",\"missing_count\":" << gap.missing_count
                << ",\"detail\":" << escaped_json(gap.detail) << '}';
        }
        out << "]}";
        return out.str();
    }

    std::string devices_to_json(const std::vector<AndroidDevice>& devices) {
        std::ostringstream out;
        out << "{\"schema\":\"termin.profiler.devices\",\"schema_version\":1,\"devices\":[";
        for (std::size_t index = 0; index < devices.size(); ++index) {
            if (index != 0) {
                out << ',';
            }
            const AndroidDevice& device = devices[index];
            out << "{\"serial\":" << escaped_json(device.serial) << ",\"state\":" << escaped_json(device.state)
                << ",\"ready\":" << (device.ready() ? "true" : "false")
                << ",\"description\":" << escaped_json(device.description) << '}';
        }
        out << "]}";
        return out.str();
    }

    bool write_text_file_atomic(const std::string& path, std::string_view content, std::string& error) {
        if (path.empty() || path == "-") {
            error = "output path must name a file";
            return false;
        }
        const std::filesystem::path destination(path);
        const std::filesystem::path temporary = destination.string() + ".termin-profiler.tmp";
        std::ofstream stream(temporary, std::ios::binary | std::ios::trunc);
        if (!stream) {
            error = "cannot open temporary output file: " + temporary.string();
            return false;
        }
        stream.write(content.data(), static_cast<std::streamsize>(content.size()));
        stream.flush();
        if (!stream) {
            error = "cannot write temporary output file: " + temporary.string();
            stream.close();
            std::error_code ignored;
            std::filesystem::remove(temporary, ignored);
            return false;
        }
        stream.close();
        if (!replace_file(temporary, destination, error)) {
            std::error_code ignored;
            std::filesystem::remove(temporary, ignored);
            return false;
        }
        return true;
    }

} // namespace termin::profiler_app
