#include <termin/profiler_app/session.hpp>

#include <charconv>
#include <limits>
#include <stdexcept>
#include <utility>

#include <termin/profiler_remote/client.hpp>
#include <termin/profiler_remote/wire_codec.hpp>

namespace termin::profiler_app {

    RemoteProfilerSession::RemoteProfilerSession(std::size_t capacity, double hitch_ratio)
        : connection_model_(std::make_shared<gui_native::RichTextModel>()) {
        auto source = std::make_unique<RemoteFrameProfilerSource>(capacity);
        remote_source_ = source.get();
        profiler_ = std::make_unique<FrameProfilerController>(std::move(source), hitch_ratio);
        refresh_connection_model();
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
        return true;
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
