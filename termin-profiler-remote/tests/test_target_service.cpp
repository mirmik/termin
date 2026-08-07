#include "guard_main.h"

#include <atomic>
#include <chrono>
#include <cstdint>
#include <optional>
#include <span>
#include <thread>
#include <vector>

#include <termin/profiler_remote/bounded_spsc_queue.hpp>
#include <termin/profiler_remote/client.hpp>
#include <termin/profiler_remote/target_service.hpp>

extern "C" {
#include <tc_profiler.h>
}

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>
#endif

using namespace termin::profiler_remote;
using namespace std::chrono_literals;

namespace {

#if defined(_WIN32)
    using TestSocket = SOCKET;
    constexpr TestSocket invalid_test_socket = INVALID_SOCKET;
#else
    using TestSocket = int;
    constexpr TestSocket invalid_test_socket = -1;
#endif

    void close_test_socket(TestSocket socket) {
        if (socket == invalid_test_socket) {
            return;
        }
#if defined(_WIN32)
        shutdown(socket, SD_BOTH);
        closesocket(socket);
#else
        shutdown(socket, SHUT_RDWR);
        close(socket);
#endif
    }

    bool send_all(TestSocket socket, std::span<const std::uint8_t> bytes) {
        std::size_t offset = 0;
        while (offset < bytes.size()) {
            const int sent = send(socket,
                                  reinterpret_cast<const char*>(bytes.data() + offset),
                                  static_cast<int>(bytes.size() - offset),
                                  0);
            if (sent <= 0) {
                return false;
            }
            offset += static_cast<std::size_t>(sent);
        }
        return true;
    }

    bool receive_all(TestSocket socket, std::span<std::uint8_t> bytes) {
        std::size_t offset = 0;
        while (offset < bytes.size()) {
            const int received = recv(
                socket, reinterpret_cast<char*>(bytes.data() + offset), static_cast<int>(bytes.size() - offset), 0);
            if (received <= 0) {
                return false;
            }
            offset += static_cast<std::size_t>(received);
        }
        return true;
    }

    TestSocket connect_client(std::uint16_t port) {
        const TestSocket socket = ::socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
        if (socket == invalid_test_socket) {
            return socket;
        }
#if defined(_WIN32)
        DWORD timeout = 2000;
        setsockopt(socket, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char*>(&timeout), sizeof(timeout));
#else
        timeval timeout{2, 0};
        setsockopt(socket, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
#endif
        sockaddr_in address{};
        address.sin_family = AF_INET;
        address.sin_port = htons(port);
        address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        if (connect(socket, reinterpret_cast<const sockaddr*>(&address), sizeof(address)) != 0) {
            close_test_socket(socket);
            return invalid_test_socket;
        }
        return socket;
    }

    bool send_message(TestSocket socket, const Message& message, std::uint64_t sequence) {
        const auto encoded = encode_message(message, sequence, 0);
        return encoded && send_all(socket, *encoded.value);
    }

    std::optional<DecodedMessage> receive_wire(TestSocket socket) {
        std::vector<std::uint8_t> bytes(envelope_size);
        if (!receive_all(socket, bytes)) {
            return std::nullopt;
        }
        const auto envelope = decode_envelope(bytes);
        if (!envelope) {
            return std::nullopt;
        }
        bytes.resize(envelope_size + envelope.value->payload_length);
        if (envelope.value->payload_length > 0 &&
            !receive_all(socket, std::span<std::uint8_t>(bytes).subspan(envelope_size))) {
            return std::nullopt;
        }
        auto decoded = decode_message(bytes);
        if (!decoded) {
            return std::nullopt;
        }
        return std::move(*decoded.value);
    }

    bool wait_until(const auto& predicate) {
        const auto deadline = std::chrono::steady_clock::now() + 2s;
        while (std::chrono::steady_clock::now() < deadline) {
            if (predicate()) {
                return true;
            }
            std::this_thread::sleep_for(1ms);
        }
        return predicate();
    }

    TestSocket handshake(RemoteProfilerTarget& target, const std::string& token, std::uint64_t sequence = 1) {
        const TestSocket socket = connect_client(target.status().listening_port);
        if (socket == invalid_test_socket) {
            return socket;
        }
        ClientHello hello;
        hello.authentication_token = token;
        if (!send_message(socket, hello, sequence)) {
            close_test_socket(socket);
            return invalid_test_socket;
        }
        const auto response = receive_wire(socket);
        if (!response || !std::holds_alternative<TargetHello>(response->message)) {
            close_test_socket(socket);
            return invalid_test_socket;
        }
        return socket;
    }

    void complete_profiled_frame(double start_ms) {
        const tc_profiler_frame_info info{start_ms, 16.0, 16.0, 0.0, 0};
        tc_profiler_begin_frame_with_info(&info);
        tc_profiler_begin_section("Host Frame");
        tc_profiler_begin_section("Present");
        tc_profiler_end_section();
        tc_profiler_end_section();
        tc_profiler_end_frame();
    }

    struct ProfilerCleanup {
        ~ProfilerCleanup() {
            tc_profiler_set_enabled(false);
            tc_profiler_clear_history();
        }
    };

} // namespace

TEST_CASE("Bounded SPSC queue preserves order and rejects complete newest values") {
    BoundedSpscQueue<int> queue(2);
    CHECK_EQ(queue.capacity(), 2);
    CHECK(queue.try_push(10));
    CHECK(queue.try_push(20));
    CHECK_FALSE(queue.try_push(30));
    CHECK_EQ(queue.size_approximate(), 2);

    int value = 0;
    REQUIRE(queue.try_pop(value));
    CHECK_EQ(value, 10);
    REQUIRE(queue.try_pop(value));
    CHECK_EQ(value, 20);
    CHECK_FALSE(queue.try_pop(value));
}

TEST_CASE("Client command handoff is bounded and a stopped worker restarts") {
    ClientConfig config;
    config.port = 9;
    config.authentication_token = "client-test-token";
    config.command_queue_capacity = 1;
    config.reconnect = false;
    RemoteProfilerClient client(std::move(config), [](const DecodedMessage&) {});
    REQUIRE(client.start());
    Control first;
    first.request_id = 1;
    CHECK(client.send_control(first));
    Control overflow;
    overflow.request_id = 2;
    CHECK_FALSE(client.send_control(overflow));
    CHECK_EQ(client.status().rejected_commands, 1);
    REQUIRE(wait_until([&] { return !client.status().running; }));
    REQUIRE(client.start());
    REQUIRE(wait_until([&] { return !client.status().running; }));
    CHECK_EQ(client.status().connection_attempts, 2);
    client.stop();
}

TEST_CASE("Bounded SPSC queue transfers values concurrently without loss") {
    constexpr int value_count = 20'000;
    BoundedSpscQueue<int> queue(31);
    std::atomic<bool> producer_done{false};
    std::thread producer([&] {
        for (int value = 0; value < value_count; ++value) {
            while (!queue.try_push(value)) {
                std::this_thread::yield();
            }
        }
        producer_done.store(true, std::memory_order_release);
    });

    int expected = 0;
    int value = 0;
    while (!producer_done.load(std::memory_order_acquire) || queue.size_approximate() != 0) {
        if (queue.try_pop(value)) {
            REQUIRE_EQ(value, expected++);
        } else {
            std::this_thread::yield();
        }
    }
    producer.join();
    CHECK_EQ(expected, value_count);
}

TEST_CASE("Target refuses non-loopback listeners and has idempotent lifecycle") {
    TargetServiceConfig forbidden;
    forbidden.bind_address = "0.0.0.0";
    forbidden.authentication_token = "token";
    RemoteProfilerTarget rejected(std::move(forbidden));
    CHECK_FALSE(rejected.start());

    TargetServiceConfig config;
    config.authentication_token = "token";
    RemoteProfilerTarget target(std::move(config));
    REQUIRE(target.start());
    CHECK(target.start());
    CHECK(target.status().running);
    CHECK(target.status().listening_port != 0);
    target.stop();
    target.stop();
    CHECK_FALSE(target.status().running);
    REQUIRE(target.start());
    target.stop();
}

TEST_CASE("Target rejects incompatible handshakes and accepts a reconnect") {
    TargetServiceConfig config;
    config.authentication_token = "version-token";
    RemoteProfilerTarget target(std::move(config));
    REQUIRE(target.start());

    TestSocket client = connect_client(target.status().listening_port);
    REQUIRE(client != invalid_test_socket);
    ClientHello incompatible;
    incompatible.minimum_minor = protocol_minor + 1;
    incompatible.authentication_token = "version-token";
    REQUIRE(send_message(client, incompatible, 1));
    const auto rejection = receive_wire(client);
    REQUIRE(rejection.has_value());
    CHECK(std::holds_alternative<ErrorEvent>(rejection->message));
    close_test_socket(client);
    REQUIRE(wait_until([&] { return target.status().rejected_clients == 1; }));

    client = connect_client(target.status().listening_port);
    REQUIRE(client != invalid_test_socket);
    ClientHello unauthorized;
    unauthorized.authentication_token = "wrong-token";
    REQUIRE(send_message(client, unauthorized, 2));
    const auto authentication_rejection = receive_wire(client);
    REQUIRE(authentication_rejection.has_value());
    CHECK(std::holds_alternative<ErrorEvent>(authentication_rejection->message));
    close_test_socket(client);
    REQUIRE(wait_until([&] { return target.status().rejected_clients == 2; }));

    client = handshake(target, "version-token", 2);
    REQUIRE(client != invalid_test_socket);
    close_test_socket(client);
    target.stop();
}

TEST_CASE("Target stop interrupts a stalled partial handshake") {
    TargetServiceConfig config;
    config.authentication_token = "partial-token";
    RemoteProfilerTarget target(std::move(config));
    REQUIRE(target.start());

    const TestSocket client = connect_client(target.status().listening_port);
    REQUIRE(client != invalid_test_socket);
    const auto encoded = encode_message(ClientHello{}, 1, 0);
    REQUIRE(encoded);
    REQUIRE(send_all(client, std::span<const std::uint8_t>(*encoded.value).first(envelope_size)));
    std::this_thread::sleep_for(20ms);

    const auto before = std::chrono::steady_clock::now();
    target.stop();
    const auto elapsed = std::chrono::steady_clock::now() - before;
    CHECK(elapsed < 500ms);
    close_test_socket(client);
}

TEST_CASE("Target streams real profiler frames and acknowledges frame-thread "
          "controls") {
    ProfilerCleanup cleanup;
    TargetServiceConfig config;
    config.authentication_token = "integration-token";
    config.platform = "test";
    config.abi = "host";
    config.build_type = "Debug";
    RemoteProfilerTarget target(std::move(config));
    REQUIRE(target.start());

    const TestSocket client = handshake(target, "integration-token");
    REQUIRE(client != invalid_test_socket);
    REQUIRE(send_message(client, Control{10, ControlKind::set_sections, true, 0}, 2));
    REQUIRE(send_message(client, Control{11, ControlKind::start_capture, false, 0}, 3));
    REQUIRE(wait_until([&] {
        target.pump_frame_thread();
        return target.status().capturing && target.status().profiling_sections;
    }));

    complete_profiled_frame(100.0);
    target.pump_frame_thread();

    bool saw_start_ack = false;
    bool saw_dictionary = false;
    bool saw_frame = false;
    for (int index = 0; index < 8 && !saw_frame; ++index) {
        const auto message = receive_wire(client);
        REQUIRE(message.has_value());
        if (const auto* status = std::get_if<Status>(&message->message)) {
            saw_start_ack |= status->request_id == 11 && status->capturing;
        } else if (const auto* dictionary = std::get_if<DictionaryAdd>(&message->message)) {
            saw_dictionary |= dictionary->entries.size() == 2;
        } else if (const auto* batch = std::get_if<FrameBatch>(&message->message)) {
            REQUIRE_EQ(batch->frames.size(), 1);
            CHECK(batch->frames[0].sections_profiled);
            CHECK_EQ(batch->frames[0].sections.size(), 2);
            saw_frame = true;
        }
    }
    CHECK(saw_start_ack);
    CHECK(saw_dictionary);
    CHECK(saw_frame);
    CHECK(target.status().transmitted_bytes > 0);

    REQUIRE(send_message(client, Control{12, ControlKind::pause_capture, false, 0}, 4));
    REQUIRE(wait_until([&] {
        target.pump_frame_thread();
        return !target.status().capturing;
    }));
    bool saw_pause_ack = false;
    for (int index = 0; index < 4 && !saw_pause_ack; ++index) {
        const auto message = receive_wire(client);
        REQUIRE(message.has_value());
        if (const auto* status = std::get_if<Status>(&message->message)) {
            saw_pause_ack = status->request_id == 12 && !status->capturing;
        }
    }
    CHECK(saw_pause_ack);
    close_test_socket(client);
    target.stop();
}

TEST_CASE("Disconnected overflow drops complete batches and reports the next gap") {
    ProfilerCleanup cleanup;
    TargetServiceConfig config;
    config.authentication_token = "overflow-token";
    config.outbound_queue_capacity = 1;
    config.frames_per_batch = 1;
    RemoteProfilerTarget target(std::move(config));
    REQUIRE(target.start());

    TestSocket client = handshake(target, "overflow-token");
    REQUIRE(client != invalid_test_socket);
    REQUIRE(send_message(client, Control{20, ControlKind::start_capture, false, 0}, 2));
    REQUIRE(wait_until([&] {
        target.pump_frame_thread();
        return target.status().capturing;
    }));
    (void)receive_wire(client); // start acknowledgement
    close_test_socket(client);
    REQUIRE(wait_until([&] { return !target.status().client_connected; }));

    complete_profiled_frame(200.0);
    target.pump_frame_thread();
    complete_profiled_frame(216.0);
    target.pump_frame_thread();
    complete_profiled_frame(232.0);
    target.pump_frame_thread();
    CHECK_EQ(target.status().dropped_batches, 2);
    CHECK_EQ(target.status().dropped_frames, 2);

    client = handshake(target, "overflow-token", 30);
    REQUIRE(client != invalid_test_socket);
    bool received_backlog = false;
    for (int index = 0; index < 4 && !received_backlog; ++index) {
        const auto message = receive_wire(client);
        REQUIRE(message.has_value());
        received_backlog = std::holds_alternative<FrameBatch>(message->message);
    }
    REQUIRE(received_backlog);

    complete_profiled_frame(248.0);
    target.pump_frame_thread();
    bool saw_drop = false;
    bool saw_latest = false;
    for (int index = 0; index < 6 && !saw_latest; ++index) {
        const auto message = receive_wire(client);
        REQUIRE(message.has_value());
        if (const auto* drop = std::get_if<DropEvent>(&message->message)) {
            saw_drop = drop->dropped_batches == 2 && drop->dropped_frames == 2;
        } else if (std::holds_alternative<FrameBatch>(message->message)) {
            saw_latest = true;
        }
    }
    CHECK(saw_drop);
    CHECK(saw_latest);
    close_test_socket(client);
    target.stop();
}

GUARD_TEST_MAIN();
