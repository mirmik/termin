#pragma once

#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>
#include <string>
#include <variant>
#include <vector>

#if defined(_WIN32) && defined(TERMIN_FRAMEGRAPH_REMOTE_EXPORTS)
#define TERMIN_FRAMEGRAPH_REMOTE_API __declspec(dllexport)
#elif defined(_WIN32)
#define TERMIN_FRAMEGRAPH_REMOTE_API __declspec(dllimport)
#else
#define TERMIN_FRAMEGRAPH_REMOTE_API __attribute__((visibility("default")))
#endif

namespace termin::framegraph_remote {

inline constexpr std::uint32_t wire_magic = 0x54464744U; // "TFGD"
inline constexpr std::uint16_t protocol_major = 1;
inline constexpr std::uint16_t protocol_minor = 0;
inline constexpr std::size_t envelope_size = 32;

struct WireLimits {
    static constexpr std::uint32_t max_payload_bytes = 1024U * 1024U;
    static constexpr std::uint64_t max_blob_bytes = 256ULL * 1024ULL * 1024ULL;
    static constexpr std::uint32_t max_chunk_bytes = 1024U * 1024U - 64U;
    static constexpr std::uint32_t max_chunks_per_blob = 4096;
    static constexpr std::uint32_t max_targets = 64;
    static constexpr std::uint32_t max_passes = 1024;
    static constexpr std::uint32_t max_resources = 4096;
    static constexpr std::uint32_t max_alias_groups = 1024;
    static constexpr std::uint32_t max_names_per_pass = 256;
    static constexpr std::uint32_t max_schedule_entries = 4096;
    static constexpr std::uint32_t max_name_bytes = 255;
    static constexpr std::uint32_t max_identity_bytes = 128;
    static constexpr std::uint32_t max_token_bytes = 256;
    static constexpr std::uint32_t max_detail_bytes = 512;
    static constexpr std::uint16_t max_burst_frames = 16;
    static constexpr std::uint32_t max_preview_long_edge = 4096;
    static constexpr std::uint32_t max_preview_millifps = 60'000;
};

enum class Capability : std::uint64_t {
    topology = 1ULL << 0,
    exact_snapshot = 1ULL << 1,
    live_preview = 1ULL << 2,
    burst_capture = 1ULL << 3,
    hdr_pixels = 1ULL << 4,
    depth_pixels = 1ULL << 5,
    compression = 1ULL << 6,
};

enum class MessageType : std::uint16_t {
    client_hello = 1,
    target_hello = 2,
    command = 3,
    topology_snapshot = 4,
    status = 5,
    capture_metadata = 6,
    blob_chunk = 7,
    drop = 8,
    error = 9,
};

enum class CommandKind : std::uint8_t {
    refresh_topology = 1,
    select_target = 2,
    capture_snapshot = 3,
    start_stream = 4,
    update_stream = 5,
    stop_stream = 6,
    capture_burst = 7,
    cancel = 8,
    request_status = 9,
    ping = 10,
    disconnect = 11,
};

enum class CaptureSelectorKind : std::uint8_t {
    resource = 1,
    internal_symbol = 2,
};

enum class CaptureEncoding : std::uint8_t {
    native_pixels = 1,
    rgba8 = 2,
    png = 3,
};

enum class CaptureKind : std::uint8_t {
    snapshot = 1,
    preview = 2,
    burst = 3,
};

enum class PixelFormat : std::uint16_t {
    unknown = 0,
    rgba8_unorm = 1,
    rgba16_float = 2,
    rgba32_float = 3,
    depth16_unorm = 4,
    depth32_float = 5,
};

enum class SessionState : std::uint8_t {
    idle = 1,
    waiting_topology = 2,
    waiting_capture = 3,
    streaming = 4,
    suspended = 5,
    error = 6,
};

enum class StatusCode : std::uint16_t {
    ok = 0,
    accepted = 1,
    completed = 2,
    cancelled = 3,
    stale_revision = 4,
    target_unavailable = 5,
    resource_unavailable = 6,
    limit_exceeded = 7,
};

enum class DropKind : std::uint8_t {
    command_queue = 1,
    capture_queue = 2,
    readback = 3,
    encoder = 4,
    receiver = 5,
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

enum class SelectorError {
    none,
    revision_required,
    stale_revision,
    target_required,
    resource_required,
    pass_required,
    symbol_required,
    invalid_stream_options,
    invalid_burst_options,
};

enum class BlobAssemblyError {
    none,
    already_complete,
    wrong_blob,
    wrong_chunk_count,
    out_of_order_chunk,
    wrong_offset,
    size_mismatch,
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
    std::uint64_t max_blob_bytes = WireLimits::max_blob_bytes;
    std::uint32_t max_chunk_bytes = WireLimits::max_chunk_bytes;
    std::string authentication_token;
    bool operator==(const ClientHello&) const = default;
};

struct TargetHello {
    std::uint16_t negotiated_major = protocol_major;
    std::uint16_t negotiated_minor = protocol_minor;
    std::uint64_t capabilities = 0;
    std::uint32_t process_id = 0;
    std::uint32_t max_payload_bytes = WireLimits::max_payload_bytes;
    std::uint64_t max_blob_bytes = WireLimits::max_blob_bytes;
    std::uint32_t max_chunk_bytes = WireLimits::max_chunk_bytes;
    std::string platform;
    std::string abi;
    std::string build_type;
    std::string build_id;
    bool operator==(const TargetHello&) const = default;
};

struct Command {
    std::uint64_t request_id = 0;
    CommandKind kind = CommandKind::request_status;
    std::uint64_t target_id = 0;
    std::uint64_t graph_revision = 0;
    CaptureSelectorKind selector_kind = CaptureSelectorKind::resource;
    std::uint64_t pass_id = 0;
    std::string resource;
    std::string symbol;
    CaptureEncoding encoding = CaptureEncoding::native_pixels;
    std::uint32_t max_preview_millifps = 0;
    std::uint32_t max_preview_long_edge = 0;
    std::uint16_t burst_frames = 0;
    bool operator==(const Command&) const = default;
};

struct WireTarget {
    std::uint64_t id = 0;
    std::string label;
    bool renderable = false;
    bool operator==(const WireTarget&) const = default;
};

struct WirePass {
    std::uint64_t id = 0;
    std::uint32_t authored_index = 0;
    std::string name;
    std::string type;
    bool enabled = true;
    bool passthrough = false;
    std::vector<std::string> reads;
    std::vector<std::string> writes;
    std::vector<std::string> internal_symbols;
    bool operator==(const WirePass&) const = default;
};

struct WireAliasGroup {
    std::string canonical_resource;
    std::vector<std::string> aliases;
    bool operator==(const WireAliasGroup&) const = default;
};

struct TopologySnapshot {
    std::uint64_t graph_revision = 0;
    std::uint64_t selected_target_id = 0;
    std::vector<WireTarget> targets;
    std::vector<WirePass> passes;
    std::vector<std::uint64_t> schedule;
    std::vector<std::string> resources;
    std::vector<WireAliasGroup> alias_groups;
    std::string render_stats;
    bool operator==(const TopologySnapshot&) const = default;
};

struct Status {
    std::uint64_t request_id = 0;
    std::uint64_t graph_revision = 0;
    SessionState state = SessionState::idle;
    StatusCode code = StatusCode::ok;
    std::uint32_t queue_depth = 0;
    std::uint64_t completed_captures = 0;
    std::uint64_t dropped_captures = 0;
    std::uint64_t target_time_ns = 0;
    std::string detail;
    bool operator==(const Status&) const = default;
};

struct CaptureMetadata {
    std::uint64_t request_id = 0;
    std::uint64_t graph_revision = 0;
    std::uint64_t blob_id = 0;
    std::int64_t frame_number = 0;
    CaptureKind kind = CaptureKind::snapshot;
    CaptureEncoding encoding = CaptureEncoding::native_pixels;
    PixelFormat pixel_format = PixelFormat::unknown;
    std::uint32_t width = 0;
    std::uint32_t height = 0;
    bool is_depth = false;
    bool exact = true;
    std::uint64_t byte_count = 0;
    std::uint32_t chunk_count = 0;
    std::uint16_t burst_index = 0;
    std::uint16_t burst_count = 0;
    bool operator==(const CaptureMetadata&) const = default;
};

struct BlobChunk {
    std::uint64_t blob_id = 0;
    std::uint32_t chunk_index = 0;
    std::uint32_t chunk_count = 0;
    std::uint64_t offset = 0;
    std::uint64_t total_bytes = 0;
    std::vector<std::uint8_t> bytes;
    bool operator==(const BlobChunk&) const = default;
};

struct DropEvent {
    DropKind kind = DropKind::capture_queue;
    std::uint64_t dropped_items = 0;
    std::int64_t after_frame_number = 0;
    std::uint64_t after_sequence = 0;
    bool operator==(const DropEvent&) const = default;
};

struct ErrorEvent {
    std::uint32_t code = 0;
    std::uint64_t related_request_id = 0;
    std::uint64_t graph_revision = 0;
    std::string detail;
    bool operator==(const ErrorEvent&) const = default;
};

using Message = std::variant<ClientHello, TargetHello, Command,
                             TopologySnapshot, Status, CaptureMetadata,
                             BlobChunk, DropEvent, ErrorEvent>;

struct DecodedMessage {
    Envelope envelope;
    Message message;
    bool operator==(const DecodedMessage&) const = default;
};

template <typename T>
struct CodecResult {
    std::optional<T> value;
    CodecError error = CodecError::none;
    std::string detail;
    explicit operator bool() const { return value.has_value(); }
};

struct SelectorValidation {
    SelectorError error = SelectorError::none;
    std::string detail;
    explicit operator bool() const { return error == SelectorError::none; }
};

struct BlobAssemblyResult {
    BlobAssemblyError error = BlobAssemblyError::none;
    std::string detail;
    bool complete = false;
    explicit operator bool() const { return error == BlobAssemblyError::none; }
};

class TERMIN_FRAMEGRAPH_REMOTE_API BlobAssembler {
public:
    explicit BlobAssembler(CaptureMetadata metadata);
    BlobAssemblyResult append(const BlobChunk& chunk);
    const CaptureMetadata& metadata() const { return metadata_; }
    const std::vector<std::uint8_t>& bytes() const { return bytes_; }
    bool complete() const { return complete_; }
    std::vector<std::uint8_t> take_bytes();

private:
    CaptureMetadata metadata_;
    std::vector<std::uint8_t> bytes_;
    std::uint32_t next_chunk_ = 0;
    std::uint64_t next_offset_ = 0;
    bool complete_ = false;
};

TERMIN_FRAMEGRAPH_REMOTE_API bool version_is_compatible(
    std::uint16_t major, std::uint16_t minor);
TERMIN_FRAMEGRAPH_REMOTE_API MessageType message_type(const Message& message);
TERMIN_FRAMEGRAPH_REMOTE_API CodecResult<std::vector<std::uint8_t>>
encode_message(const Message& message, std::uint64_t sequence,
               std::uint64_t session_id, std::uint16_t flags = 0);
TERMIN_FRAMEGRAPH_REMOTE_API CodecResult<Envelope>
decode_envelope(std::span<const std::uint8_t> bytes);
TERMIN_FRAMEGRAPH_REMOTE_API CodecResult<DecodedMessage>
decode_message(std::span<const std::uint8_t> bytes);
TERMIN_FRAMEGRAPH_REMOTE_API SelectorValidation validate_command(
    const Command& command, std::uint64_t current_graph_revision);

} // namespace termin::framegraph_remote
