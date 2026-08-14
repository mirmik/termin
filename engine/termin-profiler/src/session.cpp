#include <termin/profiler_app/session.hpp>

#include <algorithm>
#include <charconv>
#include <iomanip>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <utility>
#include <vector>

#include <termin/profiler_remote/client.hpp>
#include <termin/profiler_remote/wire_codec.hpp>

namespace termin::profiler_app {
    namespace {
        std::string milliseconds(double value) {
            std::ostringstream stream;
            stream << std::fixed << std::setprecision(3) << value;
            return stream.str();
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
    } // namespace

    RemoteProfilerSession::RemoteProfilerSession(std::size_t capacity, double hitch_ratio)
        : connection_model_(std::make_shared<gui_native::RichTextModel>()),
          gpu_summary_model_(std::make_shared<gui_native::RichTextModel>()),
          gpu_detail_model_(std::make_shared<gui_native::RichTextModel>()) {
        auto source = std::make_unique<RemoteFrameProfilerSource>(capacity);
        remote_source_ = source.get();
        profiler_ = std::make_unique<FrameProfilerController>(std::move(source), hitch_ratio);
        refresh_connection_model();
        refresh_gpu_presentation();
    }

    RemoteProfilerSession::~RemoteProfilerSession() {
        close();
    }

    bool RemoteProfilerSession::connect(std::string_view port_text, std::string authentication_token) {
        if (closed_) {
            publish_validation_error("The profiler session is already closed.");
            return false;
        }

        unsigned int parsed_port = 0;
        const auto parsed = std::from_chars(port_text.data(), port_text.data() + port_text.size(), parsed_port);
        if (port_text.empty() || parsed.ec != std::errc{} || parsed.ptr != port_text.data() + port_text.size() ||
            parsed_port == 0 || parsed_port > std::numeric_limits<std::uint16_t>::max()) {
            publish_validation_error("Port must be an integer in 1..65535.");
            return false;
        }
        if (authentication_token.empty()) {
            publish_validation_error("Token is required. Copy it from the ADB/SSH forwarding command.");
            return false;
        }
        if (authentication_token.size() > profiler_remote::WireLimits::max_token_bytes) {
            publish_validation_error("Token exceeds the remote profiler protocol limit.");
            return false;
        }

        profiler_remote::ClientConfig config;
        config.address = "127.0.0.1";
        config.port = static_cast<std::uint16_t>(parsed_port);
        config.authentication_token = std::move(authentication_token);
        config.reconnect = true;
        if (!remote_source_->connect(std::move(config))) {
            connection_requested_ = false;
            port_ = 0;
            publish_validation_error("Could not start the remote profiler connection worker.");
            return false;
        }

        connection_requested_ = true;
        port_ = static_cast<std::uint16_t>(parsed_port);
        observed_source_revision_ = 0;
        connection_model_->set_text("Connecting to 127.0.0.1:" + std::to_string(port_) +
                                    " through a local ADB/SSH forward...");
        return true;
    }

    void RemoteProfilerSession::disconnect() {
        if (closed_ || !remote_source_) {
            return;
        }
        remote_source_->disconnect();
        connection_requested_ = false;
        port_ = 0;
        observed_source_revision_ = 0;
        profiler_->update();
        refresh_connection_model();
    }

    void RemoteProfilerSession::close() {
        if (closed_) {
            return;
        }
        closed_ = true;
        connection_requested_ = false;
        port_ = 0;
        if (profiler_) {
            profiler_->close();
        }
        connection_model_->set_text("Profiler session closed.");
    }

    bool RemoteProfilerSession::update() {
        if (closed_) {
            return false;
        }
        const bool profiler_changed = profiler_->update();
        const std::uint64_t source_revision = remote_source_->revision();
        if (source_revision == observed_source_revision_) {
            return profiler_changed;
        }
        observed_source_revision_ = source_revision;
        refresh_connection_model();
        refresh_gpu_presentation();
        return true;
    }

    std::shared_ptr<const FrameProfilerSnapshot> RemoteProfilerSession::snapshot() const {
        return remote_source_->snapshot();
    }

    void RemoteProfilerSession::refresh_gpu_presentation() {
        const auto current = snapshot();
        std::vector<double> durations;
        durations.reserve(current->frames.size());
        double maximum = 0.0;
        for (const FrameProfilerFrame& frame : current->frames) {
            if (!frame.has_gpu_duration) {
                continue;
            }
            durations.push_back(frame.gpu_duration_ms);
            maximum = std::max(maximum, frame.gpu_duration_ms);
        }

        if (durations.empty()) {
            gpu_summary_model_->set_text("GPU: unavailable — no resolved GPU duration in " +
                                         std::to_string(current->frames.size()) + " captured frame(s).");
        } else {
            gpu_summary_model_->set_text(
                "GPU (resolved): " + std::to_string(durations.size()) + "/" + std::to_string(current->frames.size()) +
                " frames | p50 " + milliseconds(percentile(durations, 0.50)) + " ms | p95 " +
                milliseconds(percentile(durations, 0.95)) + " ms | max " + milliseconds(maximum) + " ms");
        }

        const std::int64_t selected = profiler_->selected_frame_number();
        const FrameProfilerFrame* frame = selected >= 0 ? current->find(selected) : nullptr;
        if (!frame) {
            gpu_detail_model_->set_text("Selected frame GPU: unavailable — no frame selected.");
        } else if (!frame->has_gpu_duration) {
            gpu_detail_model_->set_text("Frame " + std::to_string(frame->frame_number) +
                                        " GPU: unavailable — timing result was not reported.");
        } else {
            std::string classification = "within cadence budget";
            const bool cadence_missed = frame->missed_intervals > 0 ||
                                        (frame->target_interval_ms > 0.0 &&
                                         frame->interval_ms > frame->target_interval_ms * profiler_->hitch_ratio());
            if (cadence_missed) {
                const bool cpu_over_budget =
                    frame->target_interval_ms > 0.0 && frame->active_ms > frame->target_interval_ms;
                const bool gpu_over_budget =
                    frame->target_interval_ms > 0.0 && frame->gpu_duration_ms > frame->target_interval_ms;
                if (cpu_over_budget && gpu_over_budget)
                    classification = "CPU and GPU over budget";
                else if (cpu_over_budget)
                    classification = "CPU over budget";
                else if (gpu_over_budget)
                    classification = "GPU over budget";
                else
                    classification = "runtime/compositor pacing miss; CPU and app GPU fit budget";
            }
            gpu_detail_model_->set_text("Frame " + std::to_string(frame->frame_number) +
                                        " GPU: " + milliseconds(frame->gpu_duration_ms) + " ms (resolved duration) | " +
                                        classification + ".");
        }
    }

    bool RemoteProfilerSession::connected() const {
        if (!remote_source_) {
            return false;
        }
        return remote_source_->snapshot()->status.connected;
    }

    void RemoteProfilerSession::refresh_connection_model() {
        const auto snapshot = remote_source_->snapshot();
        if (snapshot->status.connected) {
            connection_model_->set_text("Connected to " + snapshot->identity.display_name +
                                        " via 127.0.0.1:" + std::to_string(port_) + ".");
        } else if (connection_requested_) {
            connection_model_->set_text("Waiting for 127.0.0.1:" + std::to_string(port_) + ": " +
                                        snapshot->status.detail);
        } else {
            connection_model_->set_text(
                "Disconnected. Create an ADB/SSH forward, then enter its port and per-launch token.");
        }
    }

    void RemoteProfilerSession::publish_validation_error(std::string detail) {
        connection_model_->set_text("Connection error: " + std::move(detail));
    }

} // namespace termin::profiler_app
