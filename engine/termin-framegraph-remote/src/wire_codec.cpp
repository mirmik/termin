#include <termin/framegraph_remote/wire_codec.hpp>

#include <bit>
#include <limits>
#include <type_traits>
#include <unordered_set>

#include <tcbase/tc_log.h>

namespace termin::framegraph_remote {
    namespace {

        using Bytes = std::vector<std::uint8_t>;

        template <typename T> CodecResult<T> failure(CodecError error, std::string detail) {
            tc_log_error("remote framegraph wire codec: %s", detail.c_str());
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
            void i64(std::int64_t value) {
                u64(std::bit_cast<std::uint64_t>(value));
            }
            void string(const std::string& value) {
                u16(static_cast<std::uint16_t>(value.size()));
                bytes_.insert(bytes_.end(), value.begin(), value.end());
            }
            void bytes(std::span<const std::uint8_t> value) {
                bytes_.insert(bytes_.end(), value.begin(), value.end());
            }
            const Bytes& data() const {
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
                std::uint8_t a = 0;
                std::uint8_t b = 0;
                if (!u8(a) || !u8(b))
                    return false;
                value = (static_cast<std::uint16_t>(a) << 8) | b;
                return true;
            }
            bool u32(std::uint32_t& value) {
                std::uint16_t a = 0;
                std::uint16_t b = 0;
                if (!u16(a) || !u16(b))
                    return false;
                value = (static_cast<std::uint32_t>(a) << 16) | b;
                return true;
            }
            bool u64(std::uint64_t& value) {
                std::uint32_t a = 0;
                std::uint32_t b = 0;
                if (!u32(a) || !u32(b))
                    return false;
                value = (static_cast<std::uint64_t>(a) << 32) | b;
                return true;
            }
            bool i64(std::int64_t& value) {
                std::uint64_t bits = 0;
                if (!u64(bits))
                    return false;
                value = std::bit_cast<std::int64_t>(bits);
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
                    detail_ = std::string(field) + " exceeds its hard length limit";
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
                    detail_ = std::string(field) + " count exceeds its hard limit";
                    return false;
                }
                return true;
            }
            bool byte_vector(Bytes& value, std::uint32_t limit, const char* field) {
                std::uint32_t length = 0;
                if (!count(length, limit, field) || !available(length))
                    return false;
                value.assign(bytes_.begin() + static_cast<std::ptrdiff_t>(position_),
                             bytes_.begin() + static_cast<std::ptrdiff_t>(position_ + length));
                position_ += length;
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

        bool valid_command_kind(CommandKind value) {
            const auto raw = static_cast<std::uint8_t>(value);
            return raw >= static_cast<std::uint8_t>(CommandKind::refresh_topology) &&
                   raw <= static_cast<std::uint8_t>(CommandKind::disconnect);
        }

        bool valid_selector_kind(CaptureSelectorKind value) {
            return value == CaptureSelectorKind::resource || value == CaptureSelectorKind::internal_symbol;
        }

        bool valid_encoding(CaptureEncoding value) {
            return value == CaptureEncoding::native_pixels || value == CaptureEncoding::rgba8 ||
                   value == CaptureEncoding::png;
        }

        bool valid_capture_kind(CaptureKind value) {
            return value == CaptureKind::snapshot || value == CaptureKind::preview || value == CaptureKind::burst;
        }

        bool valid_pixel_format(PixelFormat value) {
            const auto raw = static_cast<std::uint16_t>(value);
            return raw <= static_cast<std::uint16_t>(PixelFormat::depth32_float);
        }

        bool valid_session_state(SessionState value) {
            const auto raw = static_cast<std::uint8_t>(value);
            return raw >= static_cast<std::uint8_t>(SessionState::idle) &&
                   raw <= static_cast<std::uint8_t>(SessionState::error);
        }

        bool valid_status_code(StatusCode value) {
            return static_cast<std::uint16_t>(value) <= static_cast<std::uint16_t>(StatusCode::limit_exceeded);
        }

        bool valid_drop_kind(DropKind value) {
            const auto raw = static_cast<std::uint8_t>(value);
            return raw >= static_cast<std::uint8_t>(DropKind::command_queue) &&
                   raw <= static_cast<std::uint8_t>(DropKind::receiver);
        }

        bool valid_name(const std::string& value) {
            return !value.empty() && value.size() <= WireLimits::max_name_bytes;
        }

        bool valid_hello_limits(std::uint32_t payload, std::uint64_t blob, std::uint32_t chunk) {
            return payload > 0 && payload <= WireLimits::max_payload_bytes && blob > 0 &&
                   blob <= WireLimits::max_blob_bytes && chunk > 0 && chunk <= WireLimits::max_chunk_bytes &&
                   chunk < payload;
        }

        template <typename T> bool read_enum_u8(Reader& reader, T& value) {
            std::uint8_t raw = 0;
            if (!reader.u8(raw))
                return false;
            value = static_cast<T>(raw);
            return true;
        }

        template <typename T> bool read_enum_u16(Reader& reader, T& value) {
            std::uint16_t raw = 0;
            if (!reader.u16(raw))
                return false;
            value = static_cast<T>(raw);
            return true;
        }

        CodecResult<Bytes> invalid_value(std::string detail) {
            return failure<Bytes>(CodecError::invalid_value, std::move(detail));
        }

        CodecResult<Bytes> limit_error(std::string detail) {
            return failure<Bytes>(CodecError::limit_exceeded, std::move(detail));
        }

        bool encode_string_list(Writer& out,
                                const std::vector<std::string>& values,
                                std::uint32_t max_count,
                                const char* field,
                                std::string& error) {
            if (values.size() > max_count) {
                error = std::string(field) + " count exceeds hard limit";
                return false;
            }
            out.u32(static_cast<std::uint32_t>(values.size()));
            for (const auto& value : values) {
                if (!valid_name(value)) {
                    error = std::string(field) + " contains an empty or oversized name";
                    return false;
                }
                out.string(value);
            }
            return true;
        }

        bool
        decode_string_list(Reader& in, std::vector<std::string>& values, std::uint32_t max_count, const char* field) {
            std::uint32_t count = 0;
            if (!in.count(count, max_count, field))
                return false;
            values.reserve(count);
            for (std::uint32_t i = 0; i < count; ++i) {
                std::string value;
                if (!in.string(value, WireLimits::max_name_bytes, field))
                    return false;
                if (!valid_name(value))
                    return false;
                values.push_back(std::move(value));
            }
            return true;
        }

        std::optional<CodecResult<Bytes>> encode_payload(const Message& message, Writer& out) {
            return std::visit(
                [&](const auto& value) -> std::optional<CodecResult<Bytes>> {
                    using T = std::decay_t<decltype(value)>;
                    if constexpr (std::is_same_v<T, ClientHello>) {
                        if (value.minimum_major == 0)
                            return invalid_value("ClientHello minimum major is zero");
                        if (!valid_hello_limits(value.max_payload_bytes, value.max_blob_bytes, value.max_chunk_bytes))
                            return limit_error("ClientHello advertises invalid limits");
                        if (value.authentication_token.empty() ||
                            value.authentication_token.size() > WireLimits::max_token_bytes)
                            return limit_error("ClientHello token length is outside hard limits");
                        out.u16(value.minimum_major);
                        out.u16(value.minimum_minor);
                        out.u64(value.capabilities);
                        out.u32(value.max_payload_bytes);
                        out.u64(value.max_blob_bytes);
                        out.u32(value.max_chunk_bytes);
                        out.string(value.authentication_token);
                    } else if constexpr (std::is_same_v<T, TargetHello>) {
                        if (!version_is_compatible(value.negotiated_major, value.negotiated_minor))
                            return invalid_value("TargetHello selected incompatible version");
                        if (!valid_hello_limits(value.max_payload_bytes, value.max_blob_bytes, value.max_chunk_bytes))
                            return limit_error("TargetHello advertises invalid limits");
                        for (const auto* field : {&value.platform, &value.abi, &value.build_type, &value.build_id}) {
                            if (field->size() > WireLimits::max_identity_bytes)
                                return limit_error("TargetHello identity exceeds hard limit");
                        }
                        out.u16(value.negotiated_major);
                        out.u16(value.negotiated_minor);
                        out.u64(value.capabilities);
                        out.u32(value.process_id);
                        out.u32(value.max_payload_bytes);
                        out.u64(value.max_blob_bytes);
                        out.u32(value.max_chunk_bytes);
                        out.string(value.platform);
                        out.string(value.abi);
                        out.string(value.build_type);
                        out.string(value.build_id);
                    } else if constexpr (std::is_same_v<T, Command>) {
                        if (!valid_command_kind(value.kind) || !valid_selector_kind(value.selector_kind) ||
                            !valid_encoding(value.encoding))
                            return invalid_value("Command contains an unknown enum value");
                        if (value.resource.size() > WireLimits::max_name_bytes ||
                            value.symbol.size() > WireLimits::max_name_bytes)
                            return limit_error("Command selector exceeds hard length limit");
                        const auto validation =
                            validate_command(value, value.graph_revision == 0 ? 1 : value.graph_revision);
                        if (!validation)
                            return invalid_value("Command is invalid: " + validation.detail);
                        out.u64(value.request_id);
                        out.u8(static_cast<std::uint8_t>(value.kind));
                        out.u64(value.target_id);
                        out.u64(value.graph_revision);
                        out.u8(static_cast<std::uint8_t>(value.selector_kind));
                        out.u64(value.pass_id);
                        out.string(value.resource);
                        out.string(value.symbol);
                        out.u8(static_cast<std::uint8_t>(value.encoding));
                        out.u32(value.max_preview_millifps);
                        out.u32(value.max_preview_long_edge);
                        out.u16(value.burst_frames);
                    } else if constexpr (std::is_same_v<T, TopologySnapshot>) {
                        if (value.graph_revision == 0)
                            return invalid_value("TopologySnapshot revision is zero");
                        if (value.targets.size() > WireLimits::max_targets ||
                            value.passes.size() > WireLimits::max_passes ||
                            value.schedule.size() > WireLimits::max_schedule_entries ||
                            value.resources.size() > WireLimits::max_resources ||
                            value.alias_groups.size() > WireLimits::max_alias_groups ||
                            value.render_stats.size() > WireLimits::max_detail_bytes)
                            return limit_error("TopologySnapshot exceeds a hard limit");
                        std::unordered_set<std::uint64_t> target_ids;
                        std::unordered_set<std::uint64_t> pass_ids;
                        out.u64(value.graph_revision);
                        out.u64(value.selected_target_id);
                        out.u32(static_cast<std::uint32_t>(value.targets.size()));
                        for (const auto& target : value.targets) {
                            if (target.id == 0 || !valid_name(target.label) || !target_ids.insert(target.id).second)
                                return invalid_value("TopologySnapshot has invalid target identity");
                            out.u64(target.id);
                            out.string(target.label);
                            out.u8(target.renderable ? 1 : 0);
                        }
                        if (value.selected_target_id != 0 && !target_ids.contains(value.selected_target_id))
                            return invalid_value("TopologySnapshot selected target is absent");
                        out.u32(static_cast<std::uint32_t>(value.passes.size()));
                        for (const auto& pass : value.passes) {
                            if (pass.id == 0 || !pass_ids.insert(pass.id).second || !valid_name(pass.name) ||
                                !valid_name(pass.type))
                                return invalid_value("TopologySnapshot has invalid pass identity");
                            out.u64(pass.id);
                            out.u32(pass.authored_index);
                            out.string(pass.name);
                            out.string(pass.type);
                            out.u8(pass.enabled ? 1 : 0);
                            out.u8(pass.passthrough ? 1 : 0);
                            std::string error;
                            if (!encode_string_list(
                                    out, pass.reads, WireLimits::max_names_per_pass, "pass reads", error) ||
                                !encode_string_list(
                                    out, pass.writes, WireLimits::max_names_per_pass, "pass writes", error) ||
                                !encode_string_list(
                                    out, pass.internal_symbols, WireLimits::max_names_per_pass, "pass symbols", error))
                                return limit_error(std::move(error));
                        }
                        out.u32(static_cast<std::uint32_t>(value.schedule.size()));
                        for (std::uint64_t pass_id : value.schedule) {
                            if (!pass_ids.contains(pass_id))
                                return invalid_value("TopologySnapshot schedule references missing pass");
                            out.u64(pass_id);
                        }
                        std::string error;
                        if (!encode_string_list(out, value.resources, WireLimits::max_resources, "resources", error))
                            return limit_error(std::move(error));
                        out.u32(static_cast<std::uint32_t>(value.alias_groups.size()));
                        for (const auto& group : value.alias_groups) {
                            if (!valid_name(group.canonical_resource))
                                return invalid_value("Alias group canonical resource is invalid");
                            out.string(group.canonical_resource);
                            if (!encode_string_list(out, group.aliases, WireLimits::max_resources, "aliases", error))
                                return limit_error(std::move(error));
                        }
                        out.string(value.render_stats);
                    } else if constexpr (std::is_same_v<T, Status>) {
                        if (!valid_session_state(value.state) || !valid_status_code(value.code))
                            return invalid_value("Status contains an unknown enum value");
                        if (value.detail.size() > WireLimits::max_detail_bytes)
                            return limit_error("Status detail exceeds hard limit");
                        out.u64(value.request_id);
                        out.u64(value.graph_revision);
                        out.u8(static_cast<std::uint8_t>(value.state));
                        out.u16(static_cast<std::uint16_t>(value.code));
                        out.u32(value.queue_depth);
                        out.u64(value.completed_captures);
                        out.u64(value.dropped_captures);
                        out.u64(value.target_time_ns);
                        out.string(value.detail);
                    } else if constexpr (std::is_same_v<T, CaptureMetadata>) {
                        if (value.request_id == 0 || value.graph_revision == 0 || value.blob_id == 0 ||
                            !valid_capture_kind(value.kind) || !valid_encoding(value.encoding) ||
                            !valid_pixel_format(value.pixel_format) || value.width == 0 || value.height == 0 ||
                            value.byte_count == 0 || value.byte_count > WireLimits::max_blob_bytes ||
                            value.chunk_count == 0 || value.chunk_count > WireLimits::max_chunks_per_blob)
                            return invalid_value("CaptureMetadata contains invalid identity or size");
                        if (value.kind == CaptureKind::burst) {
                            if (value.burst_count < 2 || value.burst_count > WireLimits::max_burst_frames ||
                                value.burst_index >= value.burst_count)
                                return invalid_value("CaptureMetadata has invalid burst position");
                        } else if (value.burst_index != 0 || value.burst_count != 0) {
                            return invalid_value("Non-burst capture contains burst metadata");
                        }
                        out.u64(value.request_id);
                        out.u64(value.graph_revision);
                        out.u64(value.blob_id);
                        out.i64(value.frame_number);
                        out.u8(static_cast<std::uint8_t>(value.kind));
                        out.u8(static_cast<std::uint8_t>(value.encoding));
                        out.u16(static_cast<std::uint16_t>(value.pixel_format));
                        out.u32(value.width);
                        out.u32(value.height);
                        out.u8(value.is_depth ? 1 : 0);
                        out.u8(value.exact ? 1 : 0);
                        out.u64(value.byte_count);
                        out.u32(value.chunk_count);
                        out.u16(value.burst_index);
                        out.u16(value.burst_count);
                    } else if constexpr (std::is_same_v<T, BlobChunk>) {
                        if (value.blob_id == 0 || value.chunk_count == 0 ||
                            value.chunk_count > WireLimits::max_chunks_per_blob ||
                            value.chunk_index >= value.chunk_count || value.total_bytes == 0 ||
                            value.total_bytes > WireLimits::max_blob_bytes || value.bytes.empty() ||
                            value.bytes.size() > WireLimits::max_chunk_bytes || value.offset > value.total_bytes ||
                            value.bytes.size() > value.total_bytes - value.offset)
                            return invalid_value("BlobChunk metadata or size is invalid");
                        out.u64(value.blob_id);
                        out.u32(value.chunk_index);
                        out.u32(value.chunk_count);
                        out.u64(value.offset);
                        out.u64(value.total_bytes);
                        out.u32(static_cast<std::uint32_t>(value.bytes.size()));
                        out.bytes(value.bytes);
                    } else if constexpr (std::is_same_v<T, DropEvent>) {
                        if (!valid_drop_kind(value.kind) || value.dropped_items == 0)
                            return invalid_value("DropEvent kind or count is invalid");
                        out.u8(static_cast<std::uint8_t>(value.kind));
                        out.u64(value.dropped_items);
                        out.i64(value.after_frame_number);
                        out.u64(value.after_sequence);
                    } else if constexpr (std::is_same_v<T, ErrorEvent>) {
                        if (value.code == 0 || value.detail.empty() ||
                            value.detail.size() > WireLimits::max_detail_bytes)
                            return invalid_value("ErrorEvent code or detail is invalid");
                        out.u32(value.code);
                        out.u64(value.related_request_id);
                        out.u64(value.graph_revision);
                        out.string(value.detail);
                    }
                    return std::nullopt;
                },
                message);
        }

        CodecResult<Message> decode_payload(MessageType type, std::span<const std::uint8_t> bytes) {
            Reader in(bytes);
            Message result;
            bool ok = false;
            switch (type) {
            case MessageType::client_hello: {
                ClientHello value;
                ok = in.u16(value.minimum_major) && in.u16(value.minimum_minor) && in.u64(value.capabilities) &&
                     in.u32(value.max_payload_bytes) && in.u64(value.max_blob_bytes) && in.u32(value.max_chunk_bytes) &&
                     in.string(value.authentication_token, WireLimits::max_token_bytes, "authentication token");
                if (ok && (value.minimum_major == 0 || value.authentication_token.empty() ||
                           !valid_hello_limits(value.max_payload_bytes, value.max_blob_bytes, value.max_chunk_bytes)))
                    return failure<Message>(CodecError::invalid_value, "ClientHello contains invalid fields");
                result = std::move(value);
                break;
            }
            case MessageType::target_hello: {
                TargetHello value;
                ok = in.u16(value.negotiated_major) && in.u16(value.negotiated_minor) && in.u64(value.capabilities) &&
                     in.u32(value.process_id) && in.u32(value.max_payload_bytes) && in.u64(value.max_blob_bytes) &&
                     in.u32(value.max_chunk_bytes) &&
                     in.string(value.platform, WireLimits::max_identity_bytes, "platform") &&
                     in.string(value.abi, WireLimits::max_identity_bytes, "ABI") &&
                     in.string(value.build_type, WireLimits::max_identity_bytes, "build type") &&
                     in.string(value.build_id, WireLimits::max_identity_bytes, "build ID");
                if (ok && !version_is_compatible(value.negotiated_major, value.negotiated_minor))
                    return failure<Message>(CodecError::incompatible_version,
                                            "TargetHello selected incompatible version");
                if (ok && !valid_hello_limits(value.max_payload_bytes, value.max_blob_bytes, value.max_chunk_bytes))
                    return failure<Message>(CodecError::limit_exceeded, "TargetHello selected invalid limits");
                result = std::move(value);
                break;
            }
            case MessageType::command: {
                Command value;
                ok = in.u64(value.request_id) && read_enum_u8(in, value.kind) && in.u64(value.target_id) &&
                     in.u64(value.graph_revision) && read_enum_u8(in, value.selector_kind) && in.u64(value.pass_id) &&
                     in.string(value.resource, WireLimits::max_name_bytes, "resource") &&
                     in.string(value.symbol, WireLimits::max_name_bytes, "symbol") &&
                     read_enum_u8(in, value.encoding) && in.u32(value.max_preview_millifps) &&
                     in.u32(value.max_preview_long_edge) && in.u16(value.burst_frames);
                if (ok && (!valid_command_kind(value.kind) || !valid_selector_kind(value.selector_kind) ||
                           !valid_encoding(value.encoding)))
                    return failure<Message>(CodecError::invalid_value, "Command contains unknown enum value");
                if (ok) {
                    const auto validation =
                        validate_command(value, value.graph_revision == 0 ? 1 : value.graph_revision);
                    if (!validation)
                        return failure<Message>(CodecError::invalid_value, "Command is invalid: " + validation.detail);
                }
                result = std::move(value);
                break;
            }
            case MessageType::topology_snapshot: {
                TopologySnapshot value;
                std::uint32_t target_count = 0;
                std::uint32_t pass_count = 0;
                std::uint32_t schedule_count = 0;
                std::uint32_t alias_count = 0;
                std::unordered_set<std::uint64_t> target_ids;
                std::unordered_set<std::uint64_t> pass_ids;
                ok = in.u64(value.graph_revision) && in.u64(value.selected_target_id) &&
                     in.count(target_count, WireLimits::max_targets, "target");
                value.targets.reserve(target_count);
                for (std::uint32_t i = 0; i < target_count && ok; ++i) {
                    WireTarget target;
                    ok = in.u64(target.id) && in.string(target.label, WireLimits::max_name_bytes, "target label") &&
                         in.boolean(target.renderable);
                    if (ok && (target.id == 0 || !valid_name(target.label) || !target_ids.insert(target.id).second))
                        return failure<Message>(CodecError::invalid_value,
                                                "TopologySnapshot target identity is invalid");
                    if (ok)
                        value.targets.push_back(std::move(target));
                }
                ok = ok && in.count(pass_count, WireLimits::max_passes, "pass");
                value.passes.reserve(pass_count);
                for (std::uint32_t i = 0; i < pass_count && ok; ++i) {
                    WirePass pass;
                    ok = in.u64(pass.id) && in.u32(pass.authored_index) &&
                         in.string(pass.name, WireLimits::max_name_bytes, "pass name") &&
                         in.string(pass.type, WireLimits::max_name_bytes, "pass type") && in.boolean(pass.enabled) &&
                         in.boolean(pass.passthrough) &&
                         decode_string_list(in, pass.reads, WireLimits::max_names_per_pass, "pass reads") &&
                         decode_string_list(in, pass.writes, WireLimits::max_names_per_pass, "pass writes") &&
                         decode_string_list(in, pass.internal_symbols, WireLimits::max_names_per_pass, "pass symbols");
                    if (ok && (pass.id == 0 || !valid_name(pass.name) || !valid_name(pass.type) ||
                               !pass_ids.insert(pass.id).second))
                        return failure<Message>(CodecError::invalid_value, "TopologySnapshot pass identity is invalid");
                    if (ok)
                        value.passes.push_back(std::move(pass));
                }
                ok = ok && in.count(schedule_count, WireLimits::max_schedule_entries, "schedule");
                value.schedule.reserve(schedule_count);
                for (std::uint32_t i = 0; i < schedule_count && ok; ++i) {
                    std::uint64_t pass_id = 0;
                    ok = in.u64(pass_id);
                    if (ok && !pass_ids.contains(pass_id))
                        return failure<Message>(CodecError::invalid_value, "Schedule references missing pass");
                    if (ok)
                        value.schedule.push_back(pass_id);
                }
                ok = ok && decode_string_list(in, value.resources, WireLimits::max_resources, "resources") &&
                     in.count(alias_count, WireLimits::max_alias_groups, "alias group");
                value.alias_groups.reserve(alias_count);
                for (std::uint32_t i = 0; i < alias_count && ok; ++i) {
                    WireAliasGroup group;
                    ok = in.string(group.canonical_resource, WireLimits::max_name_bytes, "canonical resource") &&
                         decode_string_list(in, group.aliases, WireLimits::max_resources, "aliases");
                    if (ok && !valid_name(group.canonical_resource))
                        return failure<Message>(CodecError::invalid_value, "Alias canonical resource is invalid");
                    if (ok)
                        value.alias_groups.push_back(std::move(group));
                }
                ok = ok && in.string(value.render_stats, WireLimits::max_detail_bytes, "render stats");
                if (ok && (value.graph_revision == 0 ||
                           (value.selected_target_id != 0 && !target_ids.contains(value.selected_target_id))))
                    return failure<Message>(CodecError::invalid_value,
                                            "TopologySnapshot revision/selection is invalid");
                result = std::move(value);
                break;
            }
            case MessageType::status: {
                Status value;
                ok = in.u64(value.request_id) && in.u64(value.graph_revision) && read_enum_u8(in, value.state) &&
                     read_enum_u16(in, value.code) && in.u32(value.queue_depth) && in.u64(value.completed_captures) &&
                     in.u64(value.dropped_captures) && in.u64(value.target_time_ns) &&
                     in.string(value.detail, WireLimits::max_detail_bytes, "status detail");
                if (ok && (!valid_session_state(value.state) || !valid_status_code(value.code)))
                    return failure<Message>(CodecError::invalid_value, "Status contains unknown enum value");
                result = std::move(value);
                break;
            }
            case MessageType::capture_metadata: {
                CaptureMetadata value;
                ok = in.u64(value.request_id) && in.u64(value.graph_revision) && in.u64(value.blob_id) &&
                     in.i64(value.frame_number) && read_enum_u8(in, value.kind) && read_enum_u8(in, value.encoding) &&
                     read_enum_u16(in, value.pixel_format) && in.u32(value.width) && in.u32(value.height) &&
                     in.boolean(value.is_depth) && in.boolean(value.exact) && in.u64(value.byte_count) &&
                     in.u32(value.chunk_count) && in.u16(value.burst_index) && in.u16(value.burst_count);
                if (ok) {
                    const Message probe = value;
                    Writer ignored;
                    if (auto error = encode_payload(probe, ignored))
                        return failure<Message>(error->error, std::move(error->detail));
                }
                result = value;
                break;
            }
            case MessageType::blob_chunk: {
                BlobChunk value;
                ok = in.u64(value.blob_id) && in.u32(value.chunk_index) && in.u32(value.chunk_count) &&
                     in.u64(value.offset) && in.u64(value.total_bytes) &&
                     in.byte_vector(value.bytes, WireLimits::max_chunk_bytes, "blob chunk");
                if (ok) {
                    const Message probe = value;
                    Writer ignored;
                    if (auto error = encode_payload(probe, ignored))
                        return failure<Message>(error->error, std::move(error->detail));
                }
                result = std::move(value);
                break;
            }
            case MessageType::drop: {
                DropEvent value;
                ok = read_enum_u8(in, value.kind) && in.u64(value.dropped_items) && in.i64(value.after_frame_number) &&
                     in.u64(value.after_sequence);
                if (ok && (!valid_drop_kind(value.kind) || value.dropped_items == 0))
                    return failure<Message>(CodecError::invalid_value, "DropEvent kind or count is invalid");
                result = value;
                break;
            }
            case MessageType::error: {
                ErrorEvent value;
                ok = in.u32(value.code) && in.u64(value.related_request_id) && in.u64(value.graph_revision) &&
                     in.string(value.detail, WireLimits::max_detail_bytes, "error detail");
                if (ok && (value.code == 0 || value.detail.empty()))
                    return failure<Message>(CodecError::invalid_value, "ErrorEvent code or detail is invalid");
                result = std::move(value);
                break;
            }
            }

            if (!ok) {
                const CodecError error = in.error() == CodecError::none ? CodecError::truncated : in.error();
                const std::string detail =
                    in.detail().empty() ? "message payload is truncated or invalid" : in.detail();
                return failure<Message>(error, detail);
            }
            if (!in.finished())
                return failure<Message>(CodecError::trailing_data, "message payload contains trailing bytes");
            return {.value = std::move(result), .error = CodecError::none, .detail = {}};
        }

        bool known_message_type(std::uint16_t raw) {
            return raw >= static_cast<std::uint16_t>(MessageType::client_hello) &&
                   raw <= static_cast<std::uint16_t>(MessageType::error);
        }

        SelectorValidation selector_failure(SelectorError error, std::string detail) {
            return {.error = error, .detail = std::move(detail)};
        }

    } // namespace

    bool version_is_compatible(std::uint16_t major, std::uint16_t minor) {
        (void)minor;
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
                if constexpr (std::is_same_v<T, Command>)
                    return MessageType::command;
                if constexpr (std::is_same_v<T, TopologySnapshot>)
                    return MessageType::topology_snapshot;
                if constexpr (std::is_same_v<T, Status>)
                    return MessageType::status;
                if constexpr (std::is_same_v<T, CaptureMetadata>)
                    return MessageType::capture_metadata;
                if constexpr (std::is_same_v<T, BlobChunk>)
                    return MessageType::blob_chunk;
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
        if (payload.data().size() > WireLimits::max_payload_bytes)
            return limit_error("encoded payload exceeds hard limit");

        Writer out;
        out.u32(wire_magic);
        out.u16(protocol_major);
        out.u16(protocol_minor);
        out.u16(static_cast<std::uint16_t>(message_type(message)));
        out.u16(flags);
        out.u32(static_cast<std::uint32_t>(payload.data().size()));
        out.u64(sequence);
        out.u64(session_id);
        out.bytes(payload.data());
        return {.value = out.take(), .error = CodecError::none, .detail = {}};
    }

    CodecResult<Envelope> decode_envelope(std::span<const std::uint8_t> bytes) {
        if (bytes.size() < envelope_size)
            return failure<Envelope>(CodecError::truncated, "framegraph envelope is truncated");
        Reader in(bytes.first(envelope_size));
        std::uint32_t magic = 0;
        std::uint16_t raw_type = 0;
        Envelope envelope;
        if (!in.u32(magic) || !in.u16(envelope.major) || !in.u16(envelope.minor) || !in.u16(raw_type) ||
            !in.u16(envelope.flags) || !in.u32(envelope.payload_length) || !in.u64(envelope.sequence) ||
            !in.u64(envelope.session_id))
            return failure<Envelope>(CodecError::truncated, "framegraph envelope is truncated");
        if (magic != wire_magic)
            return failure<Envelope>(CodecError::bad_magic, "framegraph envelope has bad magic");
        if (!version_is_compatible(envelope.major, envelope.minor))
            return failure<Envelope>(CodecError::incompatible_version, "framegraph protocol major is incompatible");
        if (!known_message_type(raw_type))
            return failure<Envelope>(CodecError::unknown_message_type, "framegraph message type is unknown");
        if (envelope.payload_length > WireLimits::max_payload_bytes)
            return failure<Envelope>(CodecError::limit_exceeded, "framegraph payload exceeds hard limit");
        envelope.type = static_cast<MessageType>(raw_type);
        return {.value = envelope, .error = CodecError::none, .detail = {}};
    }

    CodecResult<DecodedMessage> decode_message(std::span<const std::uint8_t> bytes) {
        auto envelope_result = decode_envelope(bytes);
        if (!envelope_result)
            return {.value = std::nullopt, .error = envelope_result.error, .detail = std::move(envelope_result.detail)};
        Envelope envelope = *envelope_result.value;
        const std::size_t expected = envelope_size + envelope.payload_length;
        if (bytes.size() != expected)
            return failure<DecodedMessage>(CodecError::invalid_length, "framegraph envelope length mismatch");
        auto payload = decode_payload(envelope.type, bytes.subspan(envelope_size));
        if (!payload)
            return {.value = std::nullopt, .error = payload.error, .detail = std::move(payload.detail)};
        return {.value = DecodedMessage{envelope, std::move(*payload.value)}, .error = CodecError::none, .detail = {}};
    }

    SelectorValidation validate_command(const Command& command, std::uint64_t current_graph_revision) {
        if (command.request_id == 0)
            return selector_failure(SelectorError::target_required, "request_id must be non-zero");
        if (!valid_command_kind(command.kind) || !valid_selector_kind(command.selector_kind) ||
            !valid_encoding(command.encoding))
            return selector_failure(SelectorError::target_required, "command contains an unknown enum value");

        const bool topology_bound =
            command.kind == CommandKind::select_target || command.kind == CommandKind::capture_snapshot ||
            command.kind == CommandKind::start_stream || command.kind == CommandKind::update_stream ||
            command.kind == CommandKind::stop_stream || command.kind == CommandKind::capture_burst;
        if (topology_bound && command.graph_revision == 0)
            return selector_failure(SelectorError::revision_required, "topology-bound command requires graph_revision");
        if (topology_bound && command.graph_revision != current_graph_revision)
            return selector_failure(SelectorError::stale_revision, "command graph_revision is stale");
        if (topology_bound && command.target_id == 0)
            return selector_failure(SelectorError::target_required, "topology-bound command requires target_id");

        const bool captures = command.kind == CommandKind::capture_snapshot ||
                              command.kind == CommandKind::start_stream || command.kind == CommandKind::update_stream ||
                              command.kind == CommandKind::capture_burst;
        if (captures && command.selector_kind == CaptureSelectorKind::resource && !valid_name(command.resource))
            return selector_failure(SelectorError::resource_required, "resource capture requires resource name");
        if (captures && command.selector_kind == CaptureSelectorKind::internal_symbol) {
            if (command.pass_id == 0)
                return selector_failure(SelectorError::pass_required, "internal capture requires pass_id");
            if (!valid_name(command.symbol))
                return selector_failure(SelectorError::symbol_required, "internal capture requires symbol name");
        }
        const bool stream_options =
            command.kind == CommandKind::start_stream || command.kind == CommandKind::update_stream;
        if (stream_options &&
            (command.max_preview_millifps == 0 || command.max_preview_millifps > WireLimits::max_preview_millifps ||
             command.max_preview_long_edge == 0 || command.max_preview_long_edge > WireLimits::max_preview_long_edge))
            return selector_failure(SelectorError::invalid_stream_options, "stream FPS or long-edge limit is invalid");
        if (command.kind == CommandKind::capture_burst &&
            (command.burst_frames < 2 || command.burst_frames > WireLimits::max_burst_frames))
            return selector_failure(SelectorError::invalid_burst_options, "burst frame count must be in 2..16");
        return {};
    }

    BlobAssembler::BlobAssembler(CaptureMetadata metadata)
        : metadata_(std::move(metadata)) {}

    BlobAssemblyResult BlobAssembler::append(const BlobChunk& chunk) {
        auto reject = [](BlobAssemblyError error, std::string detail) {
            tc_log_error("remote framegraph blob assembler: %s", detail.c_str());
            return BlobAssemblyResult{error, std::move(detail), false};
        };
        if (complete_)
            return reject(BlobAssemblyError::already_complete, "chunk received after blob completion");
        if (chunk.blob_id != metadata_.blob_id)
            return reject(BlobAssemblyError::wrong_blob, "chunk blob_id mismatch");
        if (chunk.chunk_count != metadata_.chunk_count)
            return reject(BlobAssemblyError::wrong_chunk_count, "chunk_count differs from capture metadata");
        if (chunk.chunk_index != next_chunk_)
            return reject(BlobAssemblyError::out_of_order_chunk, "chunk index is not the next expected index");
        if (chunk.offset != next_offset_)
            return reject(BlobAssemblyError::wrong_offset, "chunk offset is not contiguous");
        if (chunk.total_bytes != metadata_.byte_count || chunk.bytes.empty() ||
            chunk.bytes.size() > metadata_.byte_count - next_offset_)
            return reject(BlobAssemblyError::size_mismatch, "chunk size or total differs from capture metadata");

        bytes_.insert(bytes_.end(), chunk.bytes.begin(), chunk.bytes.end());
        next_offset_ += chunk.bytes.size();
        ++next_chunk_;
        if (next_chunk_ == metadata_.chunk_count) {
            if (next_offset_ != metadata_.byte_count)
                return reject(BlobAssemblyError::size_mismatch, "final chunk does not complete declared blob size");
            complete_ = true;
        } else if (next_offset_ >= metadata_.byte_count) {
            return reject(BlobAssemblyError::size_mismatch, "blob bytes completed before final chunk");
        }
        return {.error = BlobAssemblyError::none, .detail = {}, .complete = complete_};
    }

    std::vector<std::uint8_t> BlobAssembler::take_bytes() {
        if (!complete_)
            return {};
        complete_ = false;
        return std::move(bytes_);
    }

} // namespace termin::framegraph_remote
