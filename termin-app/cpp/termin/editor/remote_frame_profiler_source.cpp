#include "termin/editor/remote_frame_profiler_source.hpp"

#include <algorithm>
#include <mutex>
#include <stdexcept>
#include <unordered_map>
#include <utility>

#include <tcbase/tc_log.h>

namespace termin {
    namespace {

        FrameProfilerCapabilities capabilities_for(std::uint64_t remote) {
            FrameProfilerCapabilities result = 0;
            using profiler_remote::Capability;
            if ((remote & static_cast<std::uint64_t>(Capability::cadence_capture)) != 0)
                result |= static_cast<FrameProfilerCapabilities>(FrameProfilerCapability::Capture);
            if ((remote & static_cast<std::uint64_t>(Capability::hierarchical_sections)) != 0)
                result |= static_cast<FrameProfilerCapabilities>(FrameProfilerCapability::SectionProfiling);
            if ((remote & static_cast<std::uint64_t>(Capability::clear_capture)) != 0)
                result |= static_cast<FrameProfilerCapabilities>(FrameProfilerCapability::Clear);
            return result;
        }

        FrameProfilerGapKind gap_kind(profiler_remote::GapKind kind) {
            switch (kind) {
            case profiler_remote::GapKind::capture_ring:
                return FrameProfilerGapKind::CaptureOverwrite;
            case profiler_remote::GapKind::source:
                return FrameProfilerGapKind::Source;
            case profiler_remote::GapKind::reconnect:
                return FrameProfilerGapKind::Disconnect;
            }
            return FrameProfilerGapKind::Source;
        }

    } // namespace

    class RemoteFrameProfilerSource::Impl {
    public:
        Impl(std::size_t target_capacity, CommandSender target_sender)
            : capacity(target_capacity),
              sender(std::move(target_sender)) {
            if (capacity == 0)
                throw std::invalid_argument("remote profiler capacity must be positive");
            state = std::make_shared<FrameProfilerSnapshot>();
            state->revision = 1;
            state->capacity = capacity;
            state->identity = {"remote", "pending", "Remote target"};
            state->status.connected = false;
            state->status.detail = "waiting for target handshake";
        }

        bool send(profiler_remote::ControlKind kind, bool enabled = false) {
            std::lock_guard lock(mutex);
            if (!sender || !state->status.connected)
                return false;
            profiler_remote::Control control;
            control.request_id = next_request_id++;
            control.kind = kind;
            control.enabled = enabled;
            if (!sender(control)) {
                publish_error("remote command queue is full");
                return false;
            }
            pending_commands.emplace(control.request_id, kind);
            return true;
        }

        bool ingest(const profiler_remote::DecodedMessage& decoded) {
            std::lock_guard lock(mutex);
            const bool starts_session = std::holds_alternative<profiler_remote::TargetHello>(decoded.message);
            if (decoded.envelope.session_id == 0 ||
                (!starts_session &&
                 (decoded.envelope.session_id != active_session_id || decoded.envelope.sequence <= last_sequence))) {
                tc_log_error("remote frame profiler: invalid session or sequence");
                return false;
            }
            auto next = std::make_shared<FrameProfilerSnapshot>(*state);
            bool changed =
                std::visit([&](const auto& message) { return apply(*next, decoded, message); }, decoded.message);
            if (!changed)
                return false;
            active_session_id = decoded.envelope.session_id;
            last_sequence = decoded.envelope.sequence;
            next->revision = state->revision + 1;
            state = std::move(next);
            return true;
        }

        void disconnected(std::string detail) {
            std::lock_guard lock(mutex);
            if (!state->status.connected && state->status.detail == detail)
                return;
            auto next = std::make_shared<FrameProfilerSnapshot>(*state);
            const bool was_connected = next->status.connected;
            next->status.connected = false;
            next->status.detail = std::move(detail);
            next->capabilities = 0;
            if (was_connected)
                next->gaps.push_back({FrameProfilerGapKind::Disconnect, 0, 0, 0, "transport disconnected"});
            pending_commands.clear();
            next->revision = state->revision + 1;
            state = std::move(next);
        }

        bool connect(profiler_remote::ClientConfig config) {
            disconnect_live();
            auto next_client = std::make_unique<profiler_remote::RemoteProfilerClient>(
                std::move(config),
                [this](const profiler_remote::DecodedMessage& message) { ingest(message); },
                [this](std::string detail) { disconnected(std::move(detail)); });
            profiler_remote::RemoteProfilerClient* client_view = next_client.get();
            {
                std::lock_guard lock(mutex);
                client = std::move(next_client);
                sender = [client_view](const profiler_remote::Control& control) {
                    return client_view->send_control(control);
                };
            }
            if (client_view->start())
                return true;
            disconnect_live();
            return false;
        }

        void disconnect_live() {
            std::unique_ptr<profiler_remote::RemoteProfilerClient> stopped;
            {
                std::lock_guard lock(mutex);
                sender = {};
                stopped = std::move(client);
            }
            if (stopped)
                stopped->stop();
        }

        template <typename T> bool apply(FrameProfilerSnapshot&, const profiler_remote::DecodedMessage&, const T&) {
            tc_log_error("remote frame profiler: unexpected message type from target");
            return false;
        }

        bool apply(FrameProfilerSnapshot& next,
                   const profiler_remote::DecodedMessage& decoded,
                   const profiler_remote::TargetHello& hello) {
            names.clear();
            pending_commands.clear();
            pending_gap_before = false;
            next.frames.clear();
            next.gaps.clear();
            next.identity.source_id = "remote:" + hello.platform + ":" + std::to_string(hello.process_id);
            next.identity.session_id = std::to_string(decoded.envelope.session_id);
            next.identity.display_name = hello.platform + " / " + hello.abi + " / " + hello.build_type;
            next.capabilities = capabilities_for(hello.capabilities);
            next.status.connected = true;
            next.status.capturing = hello.capturing;
            next.status.profiling_sections = hello.profiling_sections;
            next.status.detail = "remote target connected";
            return true;
        }

        bool apply(FrameProfilerSnapshot& next,
                   const profiler_remote::DecodedMessage&,
                   const profiler_remote::DictionaryAdd& dictionary) {
            auto candidate = names;
            for (const auto& entry : dictionary.entries) {
                if (candidate.contains(entry.id)) {
                    tc_log_error("remote frame profiler: duplicate dictionary id %u", entry.id);
                    return false;
                }
                if (candidate.size() >= profiler_remote::WireLimits::max_dictionary_entries) {
                    tc_log_error("remote frame profiler: dictionary hard limit reached");
                    return false;
                }
                candidate.emplace(entry.id, entry.name);
            }
            names = std::move(candidate);
            next.status.detail = "dictionary updated";
            return true;
        }

        bool apply(FrameProfilerSnapshot& next,
                   const profiler_remote::DecodedMessage&,
                   const profiler_remote::FrameBatch& batch) {
            std::vector<FrameProfilerFrame> converted;
            converted.reserve(batch.frames.size());
            for (const auto& wire : batch.frames) {
                FrameProfilerFrame frame;
                frame.frame_number = wire.frame_number;
                frame.start_time_ms = wire.start_time_ms;
                frame.interval_ms = wire.interval_ms;
                frame.active_ms = wire.active_ms;
                frame.target_interval_ms = wire.target_interval_ms;
                frame.deadline_lateness_ms = wire.deadline_lateness_ms;
                frame.missed_intervals = wire.missed_intervals;
                frame.sections_profiled = wire.sections_profiled;
                frame.sections.reserve(wire.sections.size());
                for (const auto& section : wire.sections) {
                    const auto found = names.find(section.name_id);
                    if (found == names.end()) {
                        tc_log_error("remote frame profiler: frame references unknown name %u", section.name_id);
                        return false;
                    }
                    frame.sections.push_back({found->second,
                                              section.cpu_ms,
                                              section.children_ms,
                                              section.call_count,
                                              section.parent_index,
                                              section.first_child,
                                              section.next_sibling});
                }
                if (pending_gap_before ||
                    (!next.frames.empty() && frame.frame_number != next.frames.back().frame_number + 1) ||
                    (!converted.empty() && frame.frame_number != converted.back().frame_number + 1))
                    frame.gap_before = true;
                converted.push_back(std::move(frame));
            }
            if (!converted.empty())
                pending_gap_before = false;
            for (auto& frame : converted)
                next.frames.push_back(std::move(frame));
            if (next.frames.size() > capacity) {
                const std::size_t overflow = next.frames.size() - capacity;
                const auto first = next.frames.front().frame_number;
                const auto last = next.frames[overflow - 1].frame_number;
                next.frames.erase(next.frames.begin(), next.frames.begin() + static_cast<std::ptrdiff_t>(overflow));
                next.frames.front().gap_before = true;
                next.status.dropped_frames += overflow;
                next.gaps.push_back({FrameProfilerGapKind::TransportDrop,
                                     first,
                                     last,
                                     overflow,
                                     "bounded receiver history overwritten"});
            }
            next.status.detail = "remote frames received";
            return !batch.frames.empty();
        }

        bool apply(FrameProfilerSnapshot& next,
                   const profiler_remote::DecodedMessage&,
                   const profiler_remote::GapEvent& gap) {
            const auto count = static_cast<std::uint64_t>(gap.last_missing_frame - gap.first_missing_frame + 1);
            next.gaps.push_back(
                {gap_kind(gap.kind), gap.first_missing_frame, gap.last_missing_frame, count, "target source gap"});
            return true;
        }

        bool apply(FrameProfilerSnapshot& next,
                   const profiler_remote::DecodedMessage&,
                   const profiler_remote::DropEvent& drop) {
            next.status.dropped_frames += drop.dropped_frames;
            pending_gap_before = pending_gap_before || drop.dropped_frames != 0;
            next.gaps.push_back(
                {FrameProfilerGapKind::TransportDrop, 0, 0, drop.dropped_frames, "target producer queue drop"});
            return true;
        }

        bool apply(FrameProfilerSnapshot& next,
                   const profiler_remote::DecodedMessage&,
                   const profiler_remote::Status& status) {
            next.status.capturing = status.capturing;
            next.status.profiling_sections = status.profiling_sections;
            next.status.dropped_frames = std::max(next.status.dropped_frames, status.dropped_frames);
            next.status.detail = status.detail;
            const auto pending = pending_commands.find(status.request_id);
            if (pending != pending_commands.end()) {
                if (pending->second == profiler_remote::ControlKind::clear_capture) {
                    next.frames.clear();
                    next.gaps.clear();
                }
                pending_commands.erase(pending);
            }
            return true;
        }

        bool apply(FrameProfilerSnapshot& next,
                   const profiler_remote::DecodedMessage&,
                   const profiler_remote::ErrorEvent& error) {
            next.status.detail = "target error " + std::to_string(error.code) + ": " + error.detail;
            tc_log_error("remote frame profiler: target error %u: %s", error.code, error.detail.c_str());
            return true;
        }

        void publish_error(std::string detail) {
            auto next = std::make_shared<FrameProfilerSnapshot>(*state);
            next->status.detail = std::move(detail);
            next->revision = state->revision + 1;
            state = std::move(next);
        }

        std::size_t capacity = 0;
        CommandSender sender;
        mutable std::mutex mutex;
        std::shared_ptr<FrameProfilerSnapshot> state;
        std::unordered_map<std::uint32_t, std::string> names;
        std::unordered_map<std::uint64_t, profiler_remote::ControlKind> pending_commands;
        std::uint64_t next_request_id = 1;
        std::uint64_t active_session_id = 0;
        std::uint64_t last_sequence = 0;
        bool pending_gap_before = false;
        std::unique_ptr<profiler_remote::RemoteProfilerClient> client;
    };

    RemoteFrameProfilerSource::RemoteFrameProfilerSource(std::size_t capacity, CommandSender sender)
        : impl_(std::make_unique<Impl>(capacity, std::move(sender))) {}

    RemoteFrameProfilerSource::~RemoteFrameProfilerSource() {
        impl_->disconnect_live();
    }

    std::uint64_t RemoteFrameProfilerSource::revision() const {
        std::lock_guard lock(impl_->mutex);
        return impl_->state->revision;
    }

    std::shared_ptr<const FrameProfilerSnapshot> RemoteFrameProfilerSource::snapshot() {
        std::lock_guard lock(impl_->mutex);
        return impl_->state;
    }

    bool RemoteFrameProfilerSource::start_capture() {
        return impl_->send(profiler_remote::ControlKind::start_capture);
    }
    bool RemoteFrameProfilerSource::pause_capture() {
        return impl_->send(profiler_remote::ControlKind::pause_capture);
    }
    bool RemoteFrameProfilerSource::set_section_profiling(bool enabled) {
        return impl_->send(profiler_remote::ControlKind::set_sections, enabled);
    }
    bool RemoteFrameProfilerSource::clear_capture() {
        return impl_->send(profiler_remote::ControlKind::clear_capture);
    }
    bool RemoteFrameProfilerSource::set_include_ui(bool) {
        return false;
    }
    void RemoteFrameProfilerSource::close() {
        impl_->disconnect_live();
        impl_->disconnected("remote source closed");
    }
    bool RemoteFrameProfilerSource::ingest(const profiler_remote::DecodedMessage& message) {
        return impl_->ingest(message);
    }
    bool RemoteFrameProfilerSource::connect(profiler_remote::ClientConfig config) {
        return impl_->connect(std::move(config));
    }
    void RemoteFrameProfilerSource::disconnect() {
        impl_->disconnect_live();
        impl_->disconnected("remote source disconnected");
    }
    void RemoteFrameProfilerSource::transport_disconnected(std::string detail) {
        impl_->disconnected(std::move(detail));
    }

} // namespace termin
