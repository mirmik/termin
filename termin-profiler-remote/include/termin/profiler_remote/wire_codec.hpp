#pragma once

#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>
#include <string>
#include <variant>
#include <vector>

#if defined(_WIN32) && defined(TERMIN_PROFILER_REMOTE_EXPORTS)
#define TERMIN_PROFILER_REMOTE_API __declspec(dllexport)
#elif defined(_WIN32)
#define TERMIN_PROFILER_REMOTE_API __declspec(dllimport)
#else
#define TERMIN_PROFILER_REMOTE_API __attribute__((visibility("default")))
#endif

namespace termin::profiler_remote {

    inline constexpr std::uint32_t wire_magic = 0x54505246U; // "TPRF"
    // v2 adds an explicit optional GPU-duration field to every WireFrame.
    // Frame payloads are not self-describing, so this is intentionally a
    // major break rather than silently mis-decoding v1 traffic.
    inline constexpr std::uint16_t protocol_major = 2;
    inline constexpr std::uint16_t protocol_minor = 0;
    inline constexpr std::size_t envelope_size = 32;

    struct WireLimits {
        static constexpr std::uint32_t max_payload_bytes = 1024U * 1024U;
        static constexpr std::uint32_t max_frames_per_batch = 256;
        static constexpr std::uint32_t max_sections_per_frame = 256;
        static constexpr std::uint32_t max_dictionary_entries = 4096;
        static constexpr std::uint32_t max_name_bytes = 63;
        static constexpr std::uint32_t max_identity_bytes = 128;
        static constexpr std::uint32_t max_token_bytes = 256;
        static constexpr std::uint32_t max_detail_bytes = 512;
    };

    enum class Capability : std::uint64_t {
        cadence_capture = 1ULL << 0,
        hierarchical_sections = 1ULL << 1,
        clear_capture = 1ULL << 2,
        clock_correlation = 1ULL << 3,
    };

    enum class MessageType : std::uint16_t {
        client_hello = 1,
        target_hello = 2,
        control = 3,
        status = 4,
        dictionary_add = 5,
        frame_batch = 6,
        gap = 7,
        drop = 8,
        error = 9,
    };

    enum class ControlKind : std::uint8_t {
        start_capture = 1,
        pause_capture = 2,
        set_sections = 3,
        clear_capture = 4,
        request_status = 5,
        ping = 6,
        disconnect = 7,
    };

    enum class GapKind : std::uint8_t {
        capture_ring = 1,
        source = 2,
        reconnect = 3,
    };

    enum class DropKind : std::uint8_t {
        producer_queue = 1,
        receiver_queue = 2,
    };

    enum class CodecError {
        none,
        invalid_argument,
        truncated,
        bad_magic,
        incompatible_version,
        unknown_message_type,
        invalid_length,
        limit_exceeded,
        invalid_value,
        trailing_data,
    };

    struct Envelope {
        std::uint16_t major = protocol_major;
        std::uint16_t minor = protocol_minor;
        MessageType type = MessageType::status;
        std::uint16_t flags = 0;
        std::uint32_t payload_length = 0;
        std::uint64_t sequence = 0;
        std::uint64_t session_id = 0;
        bool operator==(const Envelope&) const = default;
    };

    struct ClientHello {
        std::uint16_t minimum_major = protocol_major;
        std::uint16_t minimum_minor = 0;
        std::uint64_t capabilities = 0;
        std::uint32_t max_payload_bytes = WireLimits::max_payload_bytes;
        std::uint32_t max_frames_per_batch = WireLimits::max_frames_per_batch;
        std::uint32_t max_sections_per_frame = WireLimits::max_sections_per_frame;
        std::string authentication_token;
        bool operator==(const ClientHello&) const = default;
    };

    struct TargetHello {
        std::uint16_t negotiated_major = protocol_major;
        std::uint16_t negotiated_minor = protocol_minor;
        std::uint64_t capabilities = 0;
        std::uint64_t clock_frequency_hz = 1'000'000'000ULL;
        std::uint32_t process_id = 0;
        std::uint32_t max_payload_bytes = WireLimits::max_payload_bytes;
        std::uint32_t max_frames_per_batch = WireLimits::max_frames_per_batch;
        std::uint32_t max_sections_per_frame = WireLimits::max_sections_per_frame;
        bool capturing = false;
        bool profiling_sections = false;
        std::string platform;
        std::string abi;
        std::string build_type;
        std::string build_id;
        bool operator==(const TargetHello&) const = default;
    };

    struct Control {
        std::uint64_t request_id = 0;
        ControlKind kind = ControlKind::request_status;
        bool enabled = false;
        std::uint64_t client_time_ns = 0;
        bool operator==(const Control&) const = default;
    };

    struct Status {
        std::uint64_t request_id = 0;
        bool capturing = false;
        bool profiling_sections = false;
        std::uint64_t completed_frames = 0;
        std::uint64_t dropped_frames = 0;
        std::uint32_t queue_depth = 0;
        std::uint64_t target_time_ns = 0;
        std::string detail;
        bool operator==(const Status&) const = default;
    };

    struct DictionaryEntry {
        std::uint32_t id = 0;
        std::string name;
        bool operator==(const DictionaryEntry&) const = default;
    };

    struct DictionaryAdd {
        std::vector<DictionaryEntry> entries;
        bool operator==(const DictionaryAdd&) const = default;
    };

    struct WireSection {
        std::uint32_t name_id = 0;
        double cpu_ms = 0.0;
        double children_ms = 0.0;
        std::uint32_t call_count = 0;
        std::int32_t parent_index = -1;
        std::int32_t first_child = -1;
        std::int32_t next_sibling = -1;
        bool operator==(const WireSection&) const = default;
    };

    struct WireFrame {
        std::int64_t frame_number = 0;
        double start_time_ms = 0.0;
        double interval_ms = 0.0;
        double active_ms = 0.0;
        double target_interval_ms = 0.0;
        double deadline_lateness_ms = 0.0;
        std::uint32_t missed_intervals = 0;
        bool sections_profiled = false;
        std::vector<WireSection> sections;
        bool has_gpu_duration = false;
        double gpu_duration_ms = 0.0;
        bool operator==(const WireFrame&) const = default;
    };

    struct FrameBatch {
        std::vector<WireFrame> frames;
        bool operator==(const FrameBatch&) const = default;
    };

    struct GapEvent {
        GapKind kind = GapKind::source;
        std::int64_t first_missing_frame = 0;
        std::int64_t last_missing_frame = 0;
        std::uint64_t after_sequence = 0;
        bool operator==(const GapEvent&) const = default;
    };

    struct DropEvent {
        DropKind kind = DropKind::producer_queue;
        std::uint64_t dropped_batches = 0;
        std::uint64_t dropped_frames = 0;
        std::uint64_t after_sequence = 0;
        bool operator==(const DropEvent&) const = default;
    };

    struct ErrorEvent {
        std::uint32_t code = 0;
        std::uint64_t related_sequence = 0;
        std::string detail;
        bool operator==(const ErrorEvent&) const = default;
    };

    using Message = std::
        variant<ClientHello, TargetHello, Control, Status, DictionaryAdd, FrameBatch, GapEvent, DropEvent, ErrorEvent>;

    struct DecodedMessage {
        Envelope envelope;
        Message message;
        bool operator==(const DecodedMessage&) const = default;
    };

    template <typename T> struct CodecResult {
        std::optional<T> value;
        CodecError error = CodecError::none;
        std::string detail;

        explicit operator bool() const {
            return value.has_value();
        }
    };

    TERMIN_PROFILER_REMOTE_API bool version_is_compatible(std::uint16_t major, std::uint16_t minor);

    TERMIN_PROFILER_REMOTE_API MessageType message_type(const Message& message);

    // Parses and validates exactly the fixed envelope prefix. A stream transport
    // can use payload_length to read a bounded payload before calling
    // decode_message; payload bytes are never required by this operation.
    TERMIN_PROFILER_REMOTE_API CodecResult<Envelope> decode_envelope(std::span<const std::uint8_t> bytes);

    TERMIN_PROFILER_REMOTE_API CodecResult<std::vector<std::uint8_t>>
    encode_message(const Message& message, std::uint64_t sequence, std::uint64_t session_id, std::uint16_t flags = 0);

    TERMIN_PROFILER_REMOTE_API CodecResult<DecodedMessage> decode_message(std::span<const std::uint8_t> bytes);

} // namespace termin::profiler_remote
