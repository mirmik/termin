#include "guard_main.h"

#include <cstdint>
#include <string>
#include <vector>

#include <termin/framegraph_remote/wire_codec.hpp>
#include <termin/framegraph_remote/latest_value_slot.hpp>

using namespace termin::framegraph_remote;

namespace {

template <typename T>
void check_round_trip(const T& value, std::uint64_t sequence) {
    Message source = value;
    const auto encoded = encode_message(source, sequence, 0x1122334455667788ULL,
                                        0x23);
    REQUIRE(encoded);
    const auto decoded = decode_message(*encoded.value);
    REQUIRE(decoded);
    CHECK_EQ(decoded.value->envelope.sequence, sequence);
    CHECK_EQ(decoded.value->envelope.session_id, 0x1122334455667788ULL);
    CHECK_EQ(decoded.value->envelope.flags, 0x23);
    CHECK(decoded.value->envelope.type == message_type(source));
    REQUIRE(std::holds_alternative<T>(decoded.value->message));
    CHECK(std::get<T>(decoded.value->message) == value);
}

std::vector<std::uint8_t> encoded(const Message& message) {
    const auto result = encode_message(message, 1, 2);
    REQUIRE(result);
    return *result.value;
}

void set_u16(std::vector<std::uint8_t>& bytes, std::size_t offset,
             std::uint16_t value) {
    bytes[offset] = static_cast<std::uint8_t>(value >> 8);
    bytes[offset + 1] = static_cast<std::uint8_t>(value);
}

void set_u32(std::vector<std::uint8_t>& bytes, std::size_t offset,
             std::uint32_t value) {
    set_u16(bytes, offset, static_cast<std::uint16_t>(value >> 16));
    set_u16(bytes, offset + 2, static_cast<std::uint16_t>(value));
}

Command resource_command(CommandKind kind) {
    Command result;
    result.request_id = 17;
    result.kind = kind;
    result.target_id = 42;
    result.graph_revision = 9;
    result.selector_kind = CaptureSelectorKind::resource;
    result.resource = "OUTPUT";
    return result;
}

CaptureMetadata capture_metadata() {
    CaptureMetadata result;
    result.request_id = 17;
    result.graph_revision = 9;
    result.blob_id = 71;
    result.frame_number = 123;
    result.kind = CaptureKind::snapshot;
    result.encoding = CaptureEncoding::native_pixels;
    result.pixel_format = PixelFormat::rgba16_float;
    result.width = 2;
    result.height = 1;
    result.byte_count = 8;
    result.chunk_count = 2;
    return result;
}

} // namespace

TEST_CASE("Remote framegraph codec round-trips every v1 message family") {
    ClientHello client;
    client.capabilities = 7;
    client.authentication_token = "per-launch-token";
    check_round_trip(client, 1);

    TargetHello target;
    target.capabilities = 31;
    target.process_id = 42;
    target.platform = "Android";
    target.abi = "arm64-v8a";
    target.build_type = "Debug";
    target.build_id = "abc123";
    check_round_trip(target, 2);

    Command internal = resource_command(CommandKind::capture_snapshot);
    internal.selector_kind = CaptureSelectorKind::internal_symbol;
    internal.resource.clear();
    internal.pass_id = 77;
    internal.symbol = "shadow-map";
    check_round_trip(internal, 3);

    TopologySnapshot topology;
    topology.graph_revision = 9;
    topology.selected_target_id = 42;
    topology.targets = {{42, "Game viewport", true}};
    topology.passes = {
        {77, 0, "Shadow", "ShadowPass", true, false,
         {"DEPTH"}, {"SHADOW"}, {"shadow-map"}},
        {78, 1, "Color", "ColorPass", true, false,
         {"SHADOW"}, {"OUTPUT"}, {}},
    };
    topology.schedule = {77, 78};
    topology.resources = {"DEPTH", "SHADOW", "OUTPUT"};
    topology.alias_groups = {{"OUTPUT", {"PRESENT"}}};
    topology.render_stats = "Pipelines: 1";
    check_round_trip(topology, 4);

    check_round_trip(Status{17, 9, SessionState::waiting_capture,
                            StatusCode::accepted, 1, 3, 0, 1234, "queued"},
                     5);
    check_round_trip(capture_metadata(), 6);
    check_round_trip(BlobChunk{71, 0, 2, 0, 8, {1, 2, 3, 4}}, 7);
    check_round_trip(DropEvent{DropKind::encoder, 2, 120, 7}, 8);
    check_round_trip(ErrorEvent{501, 17, 9, "stale selector"}, 9);
}

TEST_CASE("Envelope framing and version compatibility are explicit") {
    CHECK(version_is_compatible(protocol_major, protocol_minor));
    CHECK(version_is_compatible(protocol_major, protocol_minor + 5));
    CHECK_FALSE(version_is_compatible(protocol_major + 1, 0));

    const auto bytes = encoded(Status{});
    const auto envelope = decode_envelope(
        std::span<const std::uint8_t>(bytes).first(envelope_size));
    REQUIRE(envelope);
    CHECK(envelope.value->type == MessageType::status);
    CHECK_EQ(envelope.value->payload_length, bytes.size() - envelope_size);

    auto newer_minor = bytes;
    set_u16(newer_minor, 6, protocol_minor + 1);
    CHECK(decode_message(newer_minor));

    auto newer_major = bytes;
    set_u16(newer_major, 4, protocol_major + 1);
    CHECK(decode_message(newer_major).error == CodecError::incompatible_version);
}

TEST_CASE("Malformed envelopes and payload sizes are rejected before allocation") {
    auto bytes = encoded(Status{});
    bytes[0] = 0;
    CHECK(decode_message(bytes).error == CodecError::bad_magic);

    bytes = encoded(Status{});
    set_u16(bytes, 8, 99);
    CHECK(decode_message(bytes).error == CodecError::unknown_message_type);

    bytes = encoded(Status{});
    set_u32(bytes, 12, WireLimits::max_payload_bytes + 1);
    CHECK(decode_message(bytes).error == CodecError::limit_exceeded);

    bytes = encoded(Status{});
    bytes.pop_back();
    CHECK(decode_message(bytes).error == CodecError::invalid_length);

    ClientHello oversized;
    oversized.authentication_token.assign(WireLimits::max_token_bytes + 1, 'x');
    CHECK(encode_message(oversized, 1, 2).error == CodecError::limit_exceeded);
}

TEST_CASE("Topology identity and collection limits are validated") {
    TopologySnapshot topology;
    topology.graph_revision = 1;
    topology.targets = {{1, "target", true}};
    topology.passes = {{2, 0, "pass", "type"}};
    topology.schedule = {3};
    CHECK(encode_message(topology, 1, 2).error == CodecError::invalid_value);

    topology.schedule = {2};
    topology.selected_target_id = 99;
    CHECK(encode_message(topology, 1, 2).error == CodecError::invalid_value);

    topology.selected_target_id = 1;
    topology.resources.resize(WireLimits::max_resources + 1, "resource");
    CHECK(encode_message(topology, 1, 2).error == CodecError::limit_exceeded);
}

TEST_CASE("Command validation rejects stale and incomplete selectors") {
    Command command = resource_command(CommandKind::capture_snapshot);
    CHECK(validate_command(command, 9));

    const auto stale = validate_command(command, 10);
    CHECK_FALSE(stale);
    CHECK(stale.error == SelectorError::stale_revision);

    command.resource.clear();
    CHECK(validate_command(command, 9).error == SelectorError::resource_required);

    command = resource_command(CommandKind::start_stream);
    CHECK(validate_command(command, 9).error ==
          SelectorError::invalid_stream_options);
    command.max_preview_millifps = 5'000;
    command.max_preview_long_edge = 960;
    CHECK(validate_command(command, 9));

    command = resource_command(CommandKind::capture_burst);
    command.burst_frames = 1;
    CHECK(validate_command(command, 9).error ==
          SelectorError::invalid_burst_options);
    command.burst_frames = 16;
    CHECK(validate_command(command, 9));
}

TEST_CASE("Latest preview slot bounds a slow receiver to one ready frame") {
    LatestValueSlot<int> slot;
    for (int frame = 1; frame <= 100; ++frame)
        slot.publish(frame);
    const auto latest = slot.take();
    REQUIRE(latest.has_value());
    CHECK_EQ(latest->value, 100);
    CHECK_EQ(latest->dropped_before, 99u);
    CHECK_FALSE(slot.take().has_value());

    slot.note_drop();
    slot.note_drop();
    slot.publish(101);
    const auto after_rejection = slot.take();
    REQUIRE(after_rejection.has_value());
    CHECK_EQ(after_rejection->value, 101);
    CHECK_EQ(after_rejection->dropped_before, 2u);
}

TEST_CASE("Blob assembler enforces identity ordering offsets and final size") {
    const CaptureMetadata metadata = capture_metadata();
    BlobAssembler assembler(metadata);

    const auto first = assembler.append({71, 0, 2, 0, 8, {1, 2, 3, 4}});
    REQUIRE(first);
    CHECK_FALSE(first.complete);

    const auto out_of_order = assembler.append({71, 0, 2, 4, 8, {5, 6, 7, 8}});
    CHECK_FALSE(out_of_order);
    CHECK(out_of_order.error == BlobAssemblyError::out_of_order_chunk);

    const auto second = assembler.append({71, 1, 2, 4, 8, {5, 6, 7, 8}});
    REQUIRE(second);
    CHECK(second.complete);
    CHECK(assembler.complete());
    CHECK(assembler.bytes() ==
          std::vector<std::uint8_t>({1, 2, 3, 4, 5, 6, 7, 8}));

    const auto extra = assembler.append({71, 1, 2, 4, 8, {5, 6, 7, 8}});
    CHECK(extra.error == BlobAssemblyError::already_complete);
}

TEST_CASE("Blob messages reject inconsistent metadata before buffering") {
    CaptureMetadata metadata = capture_metadata();
    metadata.byte_count = WireLimits::max_blob_bytes + 1;
    CHECK(encode_message(metadata, 1, 2).error == CodecError::invalid_value);

    BlobChunk chunk{71, 2, 2, 0, 8, {1}};
    CHECK(encode_message(chunk, 1, 2).error == CodecError::invalid_value);

    chunk = {71, 0, 2, 7, 8, {1, 2}};
    CHECK(encode_message(chunk, 1, 2).error == CodecError::invalid_value);
}

GUARD_TEST_MAIN();
