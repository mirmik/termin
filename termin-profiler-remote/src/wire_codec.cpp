#include <termin/profiler_remote/wire_codec.hpp>

#include <algorithm>
#include <bit>
#include <cmath>
#include <cstring>
#include <limits>
#include <type_traits>
#include <unordered_set>

#include <tcbase/tc_log.h>

namespace termin::profiler_remote {
    namespace {

        using Bytes = std::vector<std::uint8_t>;

        template <typename T> CodecResult<T> failure(CodecError error, std::string detail) {
            tc_log_error("remote profiler wire codec: %s", detail.c_str());
            return {.value = std::nullopt, .error = error, .detail = std::move(detail)};
        }

        class Writer {
        public:
            void u8(std::uint8_t value) {
                bytes_.push_back(value);
            }
            void u16(std::uint16_t value) {
                u8(static_cast<std::uint8_t>(value >> 8));
                u8(static_cast<std::uint8_t>(value));
            }
            void u32(std::uint32_t value) {
                u16(static_cast<std::uint16_t>(value >> 16));
                u16(static_cast<std::uint16_t>(value));
            }
            void u64(std::uint64_t value) {
                u32(static_cast<std::uint32_t>(value >> 32));
                u32(static_cast<std::uint32_t>(value));
            }
            void i32(std::int32_t value) {
                u32(std::bit_cast<std::uint32_t>(value));
            }
            void i64(std::int64_t value) {
                u64(std::bit_cast<std::uint64_t>(value));
            }
            void f64(double value) {
                u64(std::bit_cast<std::uint64_t>(value));
            }
            void string(const std::string& value) {
                u16(static_cast<std::uint16_t>(value.size()));
                bytes_.insert(bytes_.end(), value.begin(), value.end());
            }
            void append(std::span<const std::uint8_t> value) {
                bytes_.insert(bytes_.end(), value.begin(), value.end());
            }
            const Bytes& bytes() const {
                return bytes_;
            }
            Bytes take() {
                return std::move(bytes_);
            }

        private:
            Bytes bytes_;
        };

        class Reader {
        public:
            explicit Reader(std::span<const std::uint8_t> bytes)
                : bytes_(bytes) {}

            bool u8(std::uint8_t& value) {
                if (!available(1))
                    return false;
                value = bytes_[position_++];
                return true;
            }
            bool u16(std::uint16_t& value) {
                std::uint8_t a = 0, b = 0;
                if (!u8(a) || !u8(b))
                    return false;
                value = (static_cast<std::uint16_t>(a) << 8) | b;
                return true;
            }
            bool u32(std::uint32_t& value) {
                std::uint16_t a = 0, b = 0;
                if (!u16(a) || !u16(b))
                    return false;
                value = (static_cast<std::uint32_t>(a) << 16) | b;
                return true;
            }
            bool u64(std::uint64_t& value) {
                std::uint32_t a = 0, b = 0;
                if (!u32(a) || !u32(b))
                    return false;
                value = (static_cast<std::uint64_t>(a) << 32) | b;
                return true;
            }
            bool i32(std::int32_t& value) {
                std::uint32_t bits = 0;
                if (!u32(bits))
                    return false;
                value = std::bit_cast<std::int32_t>(bits);
                return true;
            }
            bool i64(std::int64_t& value) {
                std::uint64_t bits = 0;
                if (!u64(bits))
                    return false;
                value = std::bit_cast<std::int64_t>(bits);
                return true;
            }
            bool f64(double& value) {
                std::uint64_t bits = 0;
                if (!u64(bits))
                    return false;
                value = std::bit_cast<double>(bits);
                return true;
            }
            bool boolean(bool& value) {
                std::uint8_t raw = 0;
                if (!u8(raw))
                    return false;
                if (raw > 1) {
                    error_ = CodecError::invalid_value;
                    detail_ = "boolean field is neither 0 nor 1";
                    return false;
                }
                value = raw != 0;
                return true;
            }
            bool string(std::string& value, std::uint32_t limit, const char* field) {
                std::uint16_t length = 0;
                if (!u16(length))
                    return false;
                if (length > limit) {
                    error_ = CodecError::limit_exceeded;
                    detail_ = std::string(field) + " length " + std::to_string(length) + " exceeds limit " +
                              std::to_string(limit);
                    return false;
                }
                if (!available(length))
                    return false;
                value.assign(reinterpret_cast<const char*>(bytes_.data() + position_), length);
                position_ += length;
                return true;
            }
            bool count(std::uint32_t& value, std::uint32_t limit, const char* field) {
                if (!u32(value))
                    return false;
                if (value > limit) {
                    error_ = CodecError::limit_exceeded;
                    detail_ = std::string(field) + " count " + std::to_string(value) + " exceeds limit " +
                              std::to_string(limit);
                    return false;
                }
                return true;
            }
            bool finished() const {
                return position_ == bytes_.size();
            }
            std::size_t remaining() const {
                return bytes_.size() - position_;
            }
            CodecError error() const {
                return error_;
            }
            const std::string& detail() const {
                return detail_;
            }

        private:
            bool available(std::size_t count) {
                if (count <= bytes_.size() - position_)
                    return true;
                error_ = CodecError::truncated;
                detail_ = "message payload is truncated at byte " + std::to_string(position_);
                return false;
            }

            std::span<const std::uint8_t> bytes_;
            std::size_t position_ = 0;
            CodecError error_ = CodecError::none;
            std::string detail_;
        };

        bool valid_finite_nonnegative(double value) {
            return std::isfinite(value) && value >= 0.0;
        }

        bool valid_control(ControlKind kind) {
            const auto raw = static_cast<std::uint8_t>(kind);
            return raw >= static_cast<std::uint8_t>(ControlKind::start_capture) &&
                   raw <= static_cast<std::uint8_t>(ControlKind::disconnect);
        }

        bool valid_gap(GapKind kind) {
            const auto raw = static_cast<std::uint8_t>(kind);
            return raw >= static_cast<std::uint8_t>(GapKind::capture_ring) &&
                   raw <= static_cast<std::uint8_t>(GapKind::reconnect);
        }

        bool valid_drop(DropKind kind) {
            const auto raw = static_cast<std::uint8_t>(kind);
            return raw >= static_cast<std::uint8_t>(DropKind::producer_queue) &&
                   raw <= static_cast<std::uint8_t>(DropKind::receiver_queue);
        }

        CodecResult<Bytes> invalid_value(std::string detail) {
            return failure<Bytes>(CodecError::invalid_value, std::move(detail));
        }

        CodecResult<Bytes> limit_error(std::string detail) {
            return failure<Bytes>(CodecError::limit_exceeded, std::move(detail));
        }

        std::optional<CodecResult<Bytes>> encode_payload(const Message& message, Writer& out) {
            return std::visit(
                [&](const auto& value) -> std::optional<CodecResult<Bytes>> {
                    using T = std::decay_t<decltype(value)>;
                    if constexpr (std::is_same_v<T, ClientHello>) {
                        if (value.minimum_major == 0)
                            return invalid_value("ClientHello minimum major must be non-zero");
                        if (value.max_payload_bytes > WireLimits::max_payload_bytes ||
                            value.max_frames_per_batch > WireLimits::max_frames_per_batch ||
                            value.max_sections_per_frame > WireLimits::max_sections_per_frame)
                            return limit_error("ClientHello advertises a limit above the local hard limit");
                        if (value.authentication_token.size() > WireLimits::max_token_bytes)
                            return limit_error("ClientHello authentication token exceeds hard limit");
                        out.u16(value.minimum_major);
                        out.u16(value.minimum_minor);
                        out.u64(value.capabilities);
                        out.u32(value.max_payload_bytes);
                        out.u32(value.max_frames_per_batch);
                        out.u32(value.max_sections_per_frame);
                        out.string(value.authentication_token);
                    } else if constexpr (std::is_same_v<T, TargetHello>) {
                        if (!version_is_compatible(value.negotiated_major, value.negotiated_minor))
                            return invalid_value("TargetHello negotiated an incompatible version");
                        if (value.max_payload_bytes > WireLimits::max_payload_bytes ||
                            value.max_frames_per_batch > WireLimits::max_frames_per_batch ||
                            value.max_sections_per_frame > WireLimits::max_sections_per_frame)
                            return limit_error("TargetHello advertises a limit above the local hard limit");
                        for (const auto* field : {&value.platform, &value.abi, &value.build_type, &value.build_id})
                            if (field->size() > WireLimits::max_identity_bytes)
                                return limit_error("TargetHello identity string exceeds hard limit");
                        out.u16(value.negotiated_major);
                        out.u16(value.negotiated_minor);
                        out.u64(value.capabilities);
                        out.u64(value.clock_frequency_hz);
                        out.u32(value.process_id);
                        out.u32(value.max_payload_bytes);
                        out.u32(value.max_frames_per_batch);
                        out.u32(value.max_sections_per_frame);
                        out.u8(value.capturing ? 1 : 0);
                        out.u8(value.profiling_sections ? 1 : 0);
                        out.string(value.platform);
                        out.string(value.abi);
                        out.string(value.build_type);
                        out.string(value.build_id);
                    } else if constexpr (std::is_same_v<T, Control>) {
                        if (!valid_control(value.kind))
                            return invalid_value("Control has unknown command kind");
                        out.u64(value.request_id);
                        out.u8(static_cast<std::uint8_t>(value.kind));
                        out.u8(value.enabled ? 1 : 0);
                        out.u64(value.client_time_ns);
                    } else if constexpr (std::is_same_v<T, Status>) {
                        if (value.detail.size() > WireLimits::max_detail_bytes)
                            return limit_error("Status detail exceeds hard limit");
                        out.u64(value.request_id);
                        out.u8(value.capturing ? 1 : 0);
                        out.u8(value.profiling_sections ? 1 : 0);
                        out.u64(value.completed_frames);
                        out.u64(value.dropped_frames);
                        out.u32(value.queue_depth);
                        out.u64(value.target_time_ns);
                        out.string(value.detail);
                    } else if constexpr (std::is_same_v<T, DictionaryAdd>) {
                        if (value.entries.size() > WireLimits::max_dictionary_entries)
                            return limit_error("DictionaryAdd entry count exceeds hard limit");
                        std::unordered_set<std::uint32_t> ids;
                        ids.reserve(value.entries.size());
                        out.u32(static_cast<std::uint32_t>(value.entries.size()));
                        for (const auto& entry : value.entries) {
                            if (entry.id == 0 || !ids.insert(entry.id).second)
                                return invalid_value("DictionaryAdd IDs must be non-zero and unique");
                            if (entry.name.empty() || entry.name.size() > WireLimits::max_name_bytes)
                                return limit_error("DictionaryAdd name length is outside hard limits");
                            out.u32(entry.id);
                            out.string(entry.name);
                        }
                    } else if constexpr (std::is_same_v<T, FrameBatch>) {
                        if (value.frames.size() > WireLimits::max_frames_per_batch)
                            return limit_error("FrameBatch frame count exceeds hard limit");
                        out.u32(static_cast<std::uint32_t>(value.frames.size()));
                        for (const auto& frame : value.frames) {
                            if (!valid_finite_nonnegative(frame.start_time_ms) ||
                                !valid_finite_nonnegative(frame.interval_ms) ||
                                !valid_finite_nonnegative(frame.active_ms) ||
                                !valid_finite_nonnegative(frame.target_interval_ms) ||
                                !valid_finite_nonnegative(frame.deadline_lateness_ms))
                                return invalid_value("FrameBatch contains a non-finite or negative timing");
                            if (frame.sections.size() > WireLimits::max_sections_per_frame)
                                return limit_error("FrameBatch section count exceeds hard limit");
                            if (!frame.sections_profiled && !frame.sections.empty())
                                return invalid_value("FrameBatch cadence-only frame contains sections");
                            out.i64(frame.frame_number);
                            out.f64(frame.start_time_ms);
                            out.f64(frame.interval_ms);
                            out.f64(frame.active_ms);
                            out.f64(frame.target_interval_ms);
                            out.f64(frame.deadline_lateness_ms);
                            out.u32(frame.missed_intervals);
                            out.u8(frame.sections_profiled ? 1 : 0);
                            out.u32(static_cast<std::uint32_t>(frame.sections.size()));
                            const auto count = static_cast<std::int32_t>(frame.sections.size());
                            for (const auto& section : frame.sections) {
                                if (section.name_id == 0 || !valid_finite_nonnegative(section.cpu_ms) ||
                                    !valid_finite_nonnegative(section.children_ms) ||
                                    section.children_ms > section.cpu_ms || section.parent_index < -1 ||
                                    section.parent_index >= count || section.first_child < -1 ||
                                    section.first_child >= count || section.next_sibling < -1 ||
                                    section.next_sibling >= count)
                                    return invalid_value("FrameBatch contains an invalid section record");
                                out.u32(section.name_id);
                                out.f64(section.cpu_ms);
                                out.f64(section.children_ms);
                                out.u32(section.call_count);
                                out.i32(section.parent_index);
                                out.i32(section.first_child);
                                out.i32(section.next_sibling);
                            }
                        }
                    } else if constexpr (std::is_same_v<T, GapEvent>) {
                        if (!valid_gap(value.kind) || value.last_missing_frame < value.first_missing_frame)
                            return invalid_value("GapEvent has invalid kind or frame range");
                        out.u8(static_cast<std::uint8_t>(value.kind));
                        out.i64(value.first_missing_frame);
                        out.i64(value.last_missing_frame);
                        out.u64(value.after_sequence);
                    } else if constexpr (std::is_same_v<T, DropEvent>) {
                        if (!valid_drop(value.kind) || value.dropped_batches == 0 || value.dropped_frames == 0)
                            return invalid_value("DropEvent kind/counts are invalid");
                        out.u8(static_cast<std::uint8_t>(value.kind));
                        out.u64(value.dropped_batches);
                        out.u64(value.dropped_frames);
                        out.u64(value.after_sequence);
                    } else if constexpr (std::is_same_v<T, ErrorEvent>) {
                        if (value.detail.empty() || value.detail.size() > WireLimits::max_detail_bytes)
                            return limit_error("ErrorEvent detail length is outside hard limits");
                        out.u32(value.code);
                        out.u64(value.related_sequence);
                        out.string(value.detail);
                    }
                    return std::nullopt;
                },
                message);
        }

        template <typename T> bool read_enum_u8(Reader& reader, T& value) {
            std::uint8_t raw = 0;
            if (!reader.u8(raw))
                return false;
            value = static_cast<T>(raw);
            return true;
        }

        CodecResult<Message> decode_payload(MessageType type, std::span<const std::uint8_t> bytes) {
            Reader in(bytes);
            Message result;
            bool ok = false;
            switch (type) {
            case MessageType::client_hello: {
                ClientHello v;
                ok = in.u16(v.minimum_major) && in.u16(v.minimum_minor) && in.u64(v.capabilities) &&
                     in.u32(v.max_payload_bytes) && in.u32(v.max_frames_per_batch) &&
                     in.u32(v.max_sections_per_frame) &&
                     in.string(v.authentication_token, WireLimits::max_token_bytes, "authentication token");
                if (ok && (v.minimum_major == 0 || v.max_payload_bytes > WireLimits::max_payload_bytes ||
                           v.max_frames_per_batch > WireLimits::max_frames_per_batch ||
                           v.max_sections_per_frame > WireLimits::max_sections_per_frame))
                    return failure<Message>(CodecError::limit_exceeded,
                                            "ClientHello contains invalid negotiated limits");
                result = std::move(v);
                break;
            }
            case MessageType::target_hello: {
                TargetHello v;
                ok = in.u16(v.negotiated_major) && in.u16(v.negotiated_minor) && in.u64(v.capabilities) &&
                     in.u64(v.clock_frequency_hz) && in.u32(v.process_id) && in.u32(v.max_payload_bytes) &&
                     in.u32(v.max_frames_per_batch) && in.u32(v.max_sections_per_frame) && in.boolean(v.capturing) &&
                     in.boolean(v.profiling_sections) &&
                     in.string(v.platform, WireLimits::max_identity_bytes, "platform") &&
                     in.string(v.abi, WireLimits::max_identity_bytes, "ABI") &&
                     in.string(v.build_type, WireLimits::max_identity_bytes, "build type") &&
                     in.string(v.build_id, WireLimits::max_identity_bytes, "build ID");
                if (ok && !version_is_compatible(v.negotiated_major, v.negotiated_minor))
                    return failure<Message>(CodecError::incompatible_version,
                                            "TargetHello selected an incompatible protocol version");
                if (ok && (v.max_payload_bytes > WireLimits::max_payload_bytes ||
                           v.max_frames_per_batch > WireLimits::max_frames_per_batch ||
                           v.max_sections_per_frame > WireLimits::max_sections_per_frame))
                    return failure<Message>(CodecError::limit_exceeded,
                                            "TargetHello selected a limit above the local hard limit");
                result = std::move(v);
                break;
            }
            case MessageType::control: {
                Control v;
                ok = in.u64(v.request_id) && read_enum_u8(in, v.kind) && in.boolean(v.enabled) &&
                     in.u64(v.client_time_ns);
                if (ok && !valid_control(v.kind))
                    return failure<Message>(CodecError::invalid_value, "Control command kind is unknown");
                result = v;
                break;
            }
            case MessageType::status: {
                Status v;
                ok = in.u64(v.request_id) && in.boolean(v.capturing) && in.boolean(v.profiling_sections) &&
                     in.u64(v.completed_frames) && in.u64(v.dropped_frames) && in.u32(v.queue_depth) &&
                     in.u64(v.target_time_ns) && in.string(v.detail, WireLimits::max_detail_bytes, "status detail");
                result = std::move(v);
                break;
            }
            case MessageType::dictionary_add: {
                DictionaryAdd v;
                std::uint32_t count = 0;
                ok = in.count(count, WireLimits::max_dictionary_entries, "dictionary entry");
                if (ok) {
                    std::unordered_set<std::uint32_t> ids;
                    ids.reserve(count);
                    v.entries.reserve(count);
                    for (std::uint32_t i = 0; i < count && ok; ++i) {
                        DictionaryEntry entry;
                        ok = in.u32(entry.id) && in.string(entry.name, WireLimits::max_name_bytes, "section name");
                        if (ok && (entry.id == 0 || entry.name.empty() || !ids.insert(entry.id).second))
                            return failure<Message>(CodecError::invalid_value,
                                                    "DictionaryAdd has an empty name or duplicate/zero ID");
                        if (ok)
                            v.entries.push_back(std::move(entry));
                    }
                }
                result = std::move(v);
                break;
            }
            case MessageType::frame_batch: {
                FrameBatch batch;
                std::uint32_t frame_count = 0;
                ok = in.count(frame_count, WireLimits::max_frames_per_batch, "frame batch");
                if (ok)
                    batch.frames.reserve(frame_count);
                for (std::uint32_t frame_index = 0; frame_index < frame_count && ok; ++frame_index) {
                    WireFrame frame;
                    std::uint32_t section_count = 0;
                    ok = in.i64(frame.frame_number) && in.f64(frame.start_time_ms) && in.f64(frame.interval_ms) &&
                         in.f64(frame.active_ms) && in.f64(frame.target_interval_ms) &&
                         in.f64(frame.deadline_lateness_ms) && in.u32(frame.missed_intervals) &&
                         in.boolean(frame.sections_profiled) &&
                         in.count(section_count, WireLimits::max_sections_per_frame, "frame section");
                    if (ok &&
                        (!valid_finite_nonnegative(frame.start_time_ms) ||
                         !valid_finite_nonnegative(frame.interval_ms) || !valid_finite_nonnegative(frame.active_ms) ||
                         !valid_finite_nonnegative(frame.target_interval_ms) ||
                         !valid_finite_nonnegative(frame.deadline_lateness_ms) ||
                         (!frame.sections_profiled && section_count != 0)))
                        return failure<Message>(CodecError::invalid_value,
                                                "FrameBatch contains invalid timing or cadence-only sections");
                    if (ok)
                        frame.sections.reserve(section_count);
                    for (std::uint32_t section_index = 0; section_index < section_count && ok; ++section_index) {
                        WireSection section;
                        ok = in.u32(section.name_id) && in.f64(section.cpu_ms) && in.f64(section.children_ms) &&
                             in.u32(section.call_count) && in.i32(section.parent_index) &&
                             in.i32(section.first_child) && in.i32(section.next_sibling);
                        const auto count = static_cast<std::int32_t>(section_count);
                        if (ok &&
                            (section.name_id == 0 || !valid_finite_nonnegative(section.cpu_ms) ||
                             !valid_finite_nonnegative(section.children_ms) || section.children_ms > section.cpu_ms ||
                             section.parent_index < -1 || section.parent_index >= count || section.first_child < -1 ||
                             section.first_child >= count || section.next_sibling < -1 ||
                             section.next_sibling >= count))
                            return failure<Message>(CodecError::invalid_value,
                                                    "FrameBatch contains an invalid section record");
                        if (ok)
                            frame.sections.push_back(section);
                    }
                    if (ok)
                        batch.frames.push_back(std::move(frame));
                }
                result = std::move(batch);
                break;
            }
            case MessageType::gap: {
                GapEvent v;
                ok = read_enum_u8(in, v.kind) && in.i64(v.first_missing_frame) && in.i64(v.last_missing_frame) &&
                     in.u64(v.after_sequence);
                if (ok && (!valid_gap(v.kind) || v.last_missing_frame < v.first_missing_frame))
                    return failure<Message>(CodecError::invalid_value, "GapEvent kind or range is invalid");
                result = v;
                break;
            }
            case MessageType::drop: {
                DropEvent v;
                ok = read_enum_u8(in, v.kind) && in.u64(v.dropped_batches) && in.u64(v.dropped_frames) &&
                     in.u64(v.after_sequence);
                if (ok && (!valid_drop(v.kind) || v.dropped_batches == 0 || v.dropped_frames == 0))
                    return failure<Message>(CodecError::invalid_value, "DropEvent kind or counts are invalid");
                result = v;
                break;
            }
            case MessageType::error: {
                ErrorEvent v;
                ok = in.u32(v.code) && in.u64(v.related_sequence) &&
                     in.string(v.detail, WireLimits::max_detail_bytes, "error detail");
                if (ok && v.detail.empty())
                    return failure<Message>(CodecError::invalid_value, "ErrorEvent detail is empty");
                result = std::move(v);
                break;
            }
            }

            if (!ok) {
                const auto error = in.error() == CodecError::none ? CodecError::truncated : in.error();
                const auto detail = in.detail().empty() ? "message payload is truncated" : in.detail();
                return failure<Message>(error, detail);
            }
            if (!in.finished())
                return failure<Message>(CodecError::trailing_data,
                                        "message payload has " + std::to_string(in.remaining()) + " trailing bytes");
            return {.value = std::move(result), .error = CodecError::none, .detail = {}};
        }

        bool known_message_type(std::uint16_t raw) {
            return raw >= static_cast<std::uint16_t>(MessageType::client_hello) &&
                   raw <= static_cast<std::uint16_t>(MessageType::error);
        }

    } // namespace

    bool version_is_compatible(std::uint16_t major, std::uint16_t minor) {
        (void)minor;
        // Minor revisions are additive. Known message layouts remain stable and
        // can therefore be consumed from a newer peer; unknown message types are
        // rejected independently.
        return major == protocol_major;
    }

    MessageType message_type(const Message& message) {
        return std::visit(
            [](const auto& value) {
                using T = std::decay_t<decltype(value)>;
                if constexpr (std::is_same_v<T, ClientHello>)
                    return MessageType::client_hello;
                if constexpr (std::is_same_v<T, TargetHello>)
                    return MessageType::target_hello;
                if constexpr (std::is_same_v<T, Control>)
                    return MessageType::control;
                if constexpr (std::is_same_v<T, Status>)
                    return MessageType::status;
                if constexpr (std::is_same_v<T, DictionaryAdd>)
                    return MessageType::dictionary_add;
                if constexpr (std::is_same_v<T, FrameBatch>)
                    return MessageType::frame_batch;
                if constexpr (std::is_same_v<T, GapEvent>)
                    return MessageType::gap;
                if constexpr (std::is_same_v<T, DropEvent>)
                    return MessageType::drop;
                return MessageType::error;
            },
            message);
    }

    CodecResult<Bytes>
    encode_message(const Message& message, std::uint64_t sequence, std::uint64_t session_id, std::uint16_t flags) {
        Writer payload;
        if (auto error = encode_payload(message, payload))
            return std::move(*error);
        if (payload.bytes().size() > WireLimits::max_payload_bytes)
            return limit_error("encoded payload exceeds hard limit");

        Writer out;
        out.u32(wire_magic);
        out.u16(protocol_major);
        out.u16(protocol_minor);
        out.u16(static_cast<std::uint16_t>(message_type(message)));
        out.u16(flags);
        out.u32(static_cast<std::uint32_t>(payload.bytes().size()));
        out.u64(sequence);
        out.u64(session_id);
        out.append(payload.bytes());
        return {.value = out.take(), .error = CodecError::none, .detail = {}};
    }

    CodecResult<Envelope> decode_envelope(std::span<const std::uint8_t> bytes) {
        if (bytes.size() < envelope_size)
            return failure<Envelope>(CodecError::truncated,
                                     "envelope is truncated: got " + std::to_string(bytes.size()) + " of 32 bytes");

        Reader in(bytes.first(envelope_size));
        std::uint32_t magic = 0;
        std::uint16_t raw_type = 0;
        Envelope envelope;
        if (!in.u32(magic) || !in.u16(envelope.major) || !in.u16(envelope.minor) || !in.u16(raw_type) ||
            !in.u16(envelope.flags) || !in.u32(envelope.payload_length) || !in.u64(envelope.sequence) ||
            !in.u64(envelope.session_id))
            return failure<Envelope>(CodecError::truncated, "envelope is truncated");
        if (magic != wire_magic)
            return failure<Envelope>(CodecError::bad_magic, "bad wire magic value " + std::to_string(magic));
        if (!version_is_compatible(envelope.major, envelope.minor))
            return failure<Envelope>(CodecError::incompatible_version,
                                     "protocol major " + std::to_string(envelope.major) +
                                         " is incompatible with local major " + std::to_string(protocol_major));
        if (!known_message_type(raw_type))
            return failure<Envelope>(CodecError::unknown_message_type,
                                     "unknown message type " + std::to_string(raw_type));
        if (envelope.payload_length > WireLimits::max_payload_bytes)
            return failure<Envelope>(CodecError::limit_exceeded,
                                     "payload length " + std::to_string(envelope.payload_length) +
                                         " exceeds hard limit");
        envelope.type = static_cast<MessageType>(raw_type);
        return {.value = envelope, .error = CodecError::none, .detail = {}};
    }

    CodecResult<DecodedMessage> decode_message(std::span<const std::uint8_t> bytes) {
        auto envelope_result = decode_envelope(bytes);
        if (!envelope_result) {
            return {.value = std::nullopt, .error = envelope_result.error, .detail = std::move(envelope_result.detail)};
        }
        Envelope envelope = *envelope_result.value;
        const std::size_t expected = envelope_size + envelope.payload_length;
        if (bytes.size() != expected)
            return failure<DecodedMessage>(CodecError::invalid_length,
                                           "envelope declares " + std::to_string(expected) + " total bytes, received " +
                                               std::to_string(bytes.size()));

        auto payload = decode_payload(envelope.type, bytes.subspan(envelope_size));
        if (!payload) {
            return {.value = std::nullopt, .error = payload.error, .detail = std::move(payload.detail)};
        }
        return {.value = DecodedMessage{envelope, std::move(*payload.value)}, .error = CodecError::none, .detail = {}};
    }

} // namespace termin::profiler_remote
