#include "guard_main.h"

#include <cctype>
#include <cstdint>
#include <string>
#include <vector>

#include <termin/profiler_remote/wire_codec.hpp>

using namespace termin::profiler_remote;

namespace {

    std::vector<std::uint8_t> from_hex(const std::string& text) {
        std::vector<std::uint8_t> result;
        int high = -1;
        for (const unsigned char c : text) {
            if (std::isspace(c))
                continue;
            int digit = 0;
            if (c >= '0' && c <= '9')
                digit = c - '0';
            else if (c >= 'a' && c <= 'f')
                digit = c - 'a' + 10;
            else if (c >= 'A' && c <= 'F')
                digit = c - 'A' + 10;
            else
                continue;
            if (high < 0)
                high = digit;
            else {
                result.push_back(static_cast<std::uint8_t>((high << 4) | digit));
                high = -1;
            }
        }
        return result;
    }

    void set_u16(std::vector<std::uint8_t>& bytes, std::size_t offset, std::uint16_t value) {
        bytes[offset] = static_cast<std::uint8_t>(value >> 8);
        bytes[offset + 1] = static_cast<std::uint8_t>(value);
    }

    void set_u32(std::vector<std::uint8_t>& bytes, std::size_t offset, std::uint32_t value) {
        set_u16(bytes, offset, static_cast<std::uint16_t>(value >> 16));
        set_u16(bytes, offset + 2, static_cast<std::uint16_t>(value));
    }

    template <typename T> void check_round_trip(const T& value, std::uint64_t sequence) {
        Message source = value;
        auto encoded = encode_message(source, sequence, 0x1122334455667788ULL, 0x23);
        REQUIRE(encoded);
        auto decoded = decode_message(*encoded.value);
        REQUIRE(decoded);
        CHECK_EQ(decoded.value->envelope.sequence, sequence);
        CHECK_EQ(decoded.value->envelope.session_id, 0x1122334455667788ULL);
        CHECK_EQ(decoded.value->envelope.flags, 0x23);
        CHECK(decoded.value->envelope.type == message_type(source));
        REQUIRE(std::holds_alternative<T>(decoded.value->message));
        CHECK(std::get<T>(decoded.value->message) == value);
    }

    std::vector<std::uint8_t> encoded(const Message& message) {
        auto result = encode_message(message, 1, 2);
        REQUIRE(result);
        return *result.value;
    }

} // namespace

TEST_CASE("Remote profiler codec round-trips every message type") {
    ClientHello client;
    client.minimum_minor = 0;
    client.capabilities = 5;
    client.max_frames_per_batch = 12;
    client.authentication_token = "secret";
    check_round_trip(client, 1);

    TargetHello target;
    target.capabilities = 15;
    target.process_id = 42;
    target.capturing = true;
    target.profiling_sections = true;
    target.platform = "Android";
    target.abi = "arm64-v8a";
    target.build_type = "Debug";
    target.build_id = "abc123";
    check_round_trip(target, 2);

    check_round_trip(Control{17, ControlKind::set_sections, true, 123456}, 3);
    check_round_trip(Status{17, true, true, 400, 3, 2, 999, "streaming"}, 4);
    check_round_trip(DictionaryAdd{{{1, "Frame"}, {2, "Present"}}}, 5);

    WireFrame frame;
    frame.frame_number = 73;
    frame.start_time_ms = 1200.5;
    frame.interval_ms = 16.7;
    frame.active_ms = 4.25;
    frame.has_gpu_duration = true;
    frame.gpu_duration_ms = 1.75;
    frame.target_interval_ms = 16.666;
    frame.deadline_lateness_ms = 0.25;
    frame.missed_intervals = 1;
    frame.sections_profiled = true;
    frame.sections = {
        {1, 4.0, 1.5, 1, -1, 1, -1},
        {2, 1.5, 0.0, 2, 0, -1, -1},
    };
    check_round_trip(FrameBatch{{frame}}, 6);
    check_round_trip(GapEvent{GapKind::capture_ring, 80, 84, 6}, 7);
    check_round_trip(DropEvent{DropKind::producer_queue, 2, 9, 7}, 8);
    check_round_trip(ErrorEvent{501, 8, "bad command"}, 9);
}

TEST_CASE("Protocol version compatibility is explicit") {
    CHECK(version_is_compatible(protocol_major, protocol_minor));
    CHECK(version_is_compatible(protocol_major, protocol_minor + 7));
    CHECK_FALSE(version_is_compatible(protocol_major + 1, 0));

    auto bytes = encoded(Status{});
    set_u16(bytes, 6, protocol_minor + 1);
    CHECK(decode_message(bytes));
    set_u16(bytes, 4, protocol_major + 1);
    const auto incompatible = decode_message(bytes);
    CHECK_FALSE(incompatible);
    CHECK(incompatible.error == CodecError::incompatible_version);
}

TEST_CASE("Envelope can be validated before a stream reads its payload") {
    const auto bytes = encoded(Status{42, true, false, 3, 1, 0, 99, "ok"});
    const auto envelope = decode_envelope(std::span<const std::uint8_t>(bytes).first(envelope_size));
    REQUIRE(envelope);
    CHECK(envelope.value->type == MessageType::status);
    CHECK_EQ(envelope.value->sequence, 1);
    CHECK_EQ(envelope.value->session_id, 2);
    CHECK_EQ(envelope.value->payload_length, bytes.size() - envelope_size);
}

TEST_CASE("Version-two golden bytes cover every message type") {
    const std::vector<std::pair<Message, std::string>> cases = {
        {ClientHello{},
         "54505246 0002 0000 0001 0000 0000001a 0000000000000001 "
         "0000000000000002 "
         "0002 0000 0000000000000000 00100000 00000100 00000100 0000"},
        {TargetHello{},
         "54505246 0002 0000 0002 0000 0000002e 0000000000000001 "
         "0000000000000002 "
         "0002 0000 0000000000000000 000000003b9aca00 00000000 00100000 00000100 "
         "00000100 00 00 0000 0000 0000 0000"},
        {Control{},
         "54505246 0002 0000 0003 0000 00000012 0000000000000001 "
         "0000000000000002 "
         "0000000000000000 05 00 0000000000000000"},
        {Status{},
         "54505246 0002 0000 0004 0000 00000028 0000000000000001 "
         "0000000000000002 "
         "0000000000000000 00 00 0000000000000000 0000000000000000 00000000 "
         "0000000000000000 0000"},
        {DictionaryAdd{},
         "54505246 0002 0000 0005 0000 00000004 "
         "0000000000000001 0000000000000002 "
         "00000000"},
        {FrameBatch{},
         "54505246 0002 0000 0006 0000 00000004 0000000000000001 "
         "0000000000000002 "
         "00000000"},
        {GapEvent{},
         "54505246 0002 0000 0007 0000 00000019 0000000000000001 "
         "0000000000000002 "
         "02 0000000000000000 0000000000000000 0000000000000000"},
        {DropEvent{DropKind::producer_queue, 1, 1, 0},
         "54505246 0002 0000 0008 0000 00000019 0000000000000001 "
         "0000000000000002 "
         "01 0000000000000001 0000000000000001 0000000000000000"},
        {ErrorEvent{1, 0, "x"},
         "54505246 0002 0000 0009 0000 0000000f "
         "0000000000000001 0000000000000002 "
         "00000001 0000000000000000 0001 78"},
    };

    for (const auto& [message, golden] : cases) {
        const auto actual = encoded(message);
        CHECK(actual == from_hex(golden));
        CHECK(decode_message(from_hex(golden)));
    }
}

TEST_CASE("Malformed envelopes are rejected before payload allocation") {
    auto bytes = encoded(Status{});

    auto bad_magic = bytes;
    bad_magic[0] = 0;
    CHECK(decode_message(bad_magic).error == CodecError::bad_magic);

    auto unknown_type = bytes;
    set_u16(unknown_type, 8, 99);
    CHECK(decode_message(unknown_type).error == CodecError::unknown_message_type);

    auto excessive_payload = bytes;
    set_u32(excessive_payload, 12, WireLimits::max_payload_bytes + 1);
    CHECK(decode_message(excessive_payload).error == CodecError::limit_exceeded);

    auto wrong_length = bytes;
    set_u32(wrong_length, 12, 2);
    CHECK(decode_message(wrong_length).error == CodecError::invalid_length);

    bytes.resize(envelope_size - 1);
    CHECK(decode_message(bytes).error == CodecError::truncated);
}

TEST_CASE("Counts and names are bounded before reserve or assignment") {
    auto dictionary = encoded(DictionaryAdd{});
    set_u32(dictionary, envelope_size, WireLimits::max_dictionary_entries + 1);
    CHECK(decode_message(dictionary).error == CodecError::limit_exceeded);

    auto frames = encoded(FrameBatch{});
    set_u32(frames, envelope_size, WireLimits::max_frames_per_batch + 1);
    CHECK(decode_message(frames).error == CodecError::limit_exceeded);

    auto named = encoded(DictionaryAdd{{{1, "ok"}}});
    set_u16(named, envelope_size + 8, WireLimits::max_name_bytes + 1);
    CHECK(decode_message(named).error == CodecError::limit_exceeded);

    ClientHello oversized;
    oversized.authentication_token.assign(WireLimits::max_token_bytes + 1, 'x');
    CHECK(encode_message(oversized, 1, 2).error == CodecError::limit_exceeded);
}

TEST_CASE("A truncated frame batch never yields a partial decoded message") {
    WireFrame first;
    first.frame_number = 1;
    WireFrame second;
    second.frame_number = 2;
    auto bytes = encoded(FrameBatch{{first, second}});
    bytes.pop_back();
    set_u32(bytes, 12, static_cast<std::uint32_t>(bytes.size() - envelope_size));

    const auto result = decode_message(bytes);
    CHECK_FALSE(result);
    CHECK(result.error == CodecError::truncated);
    CHECK_FALSE(result.value.has_value());
}

TEST_CASE("Invalid section structure and boolean values are rejected") {
    WireFrame frame;
    frame.sections_profiled = true;
    frame.sections = {{1, 1.0, 0.0, 1, -1, -1, -1}};
    auto bytes = encoded(FrameBatch{{frame}});

    // Frame payload: count(4), frame fields, GPU presence/value, sections boolean at byte 57.
    bytes[envelope_size + 57] = 2;
    CHECK(decode_message(bytes).error == CodecError::invalid_value);

    frame.sections[0].parent_index = 5;
    CHECK(encode_message(FrameBatch{{frame}}, 1, 2).error == CodecError::invalid_value);
}

GUARD_TEST_MAIN();
