#include "guard_main.h"

#include <termin/framegraph_remote/wire_codec.hpp>
#include <termin/framegraph_remote_target/target_service.hpp>
#include <termin/render/frame_graph_debugger.hpp>
#include <termin/render/frame_pass.hpp>
#include <termin/render/rendering_manager.hpp>
#include <termin/render/tc_pass.hpp>

#include <algorithm>
#include <chrono>
#include <optional>
#include <set>
#include <span>
#include <string>
#include <thread>
#include <variant>
#include <vector>

extern "C"
{
#include <core/tc_scene.h>
#include <render/tc_display.h>
#include <render/tc_display_pool.h>
#include <render/tc_pipeline.h>
#include <render/tc_render_target.h>
#include <render/tc_viewport.h>
}

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
using TestSocket = SOCKET;
constexpr TestSocket invalid_test_socket = INVALID_SOCKET;
#else
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>
using TestSocket = int;
constexpr TestSocket invalid_test_socket = -1;
#endif

using namespace std::chrono_literals;
using namespace termin::framegraph_remote;
using termin::framegraph_remote_target::RemoteFrameGraphTarget;
using termin::framegraph_remote_target::TargetServiceConfig;

namespace
{

    void close_test_socket(TestSocket socket)
    {
        if (socket == invalid_test_socket)
            return;
#if defined(_WIN32)
        shutdown(socket, SD_BOTH);
        closesocket(socket);
#else
        shutdown(socket, SHUT_RDWR);
        close(socket);
#endif
    }

    bool send_all(TestSocket socket, std::span<const std::uint8_t> bytes)
    {
        std::size_t offset = 0;
        while (offset < bytes.size())
        {
            const int count =
                send(socket,
                     reinterpret_cast<const char*>(bytes.data() + offset),
                     static_cast<int>(bytes.size() - offset),
                     0);
            if (count <= 0)
                return false;
            offset += static_cast<std::size_t>(count);
        }
        return true;
    }

    bool receive_all(TestSocket socket, std::span<std::uint8_t> bytes)
    {
        std::size_t offset = 0;
        while (offset < bytes.size())
        {
            const int count =
                recv(socket,
                     reinterpret_cast<char*>(bytes.data() + offset),
                     static_cast<int>(bytes.size() - offset),
                     0);
            if (count <= 0)
                return false;
            offset += static_cast<std::size_t>(count);
        }
        return true;
    }

    TestSocket connect_client(std::uint16_t port)
    {
        const TestSocket socket = ::socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
        if (socket == invalid_test_socket)
            return socket;
#if defined(_WIN32)
        DWORD timeout = 2000;
        setsockopt(socket,
                   SOL_SOCKET,
                   SO_RCVTIMEO,
                   reinterpret_cast<const char*>(&timeout),
                   sizeof(timeout));
#else
        timeval timeout{2, 0};
        setsockopt(socket, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
#endif
        sockaddr_in address{};
        address.sin_family = AF_INET;
        address.sin_port = htons(port);
        address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        if (connect(socket,
                    reinterpret_cast<const sockaddr*>(&address),
                    sizeof(address)) != 0)
        {
            close_test_socket(socket);
            return invalid_test_socket;
        }
        return socket;
    }

    bool send_wire(TestSocket socket,
                   const Message& message,
                   std::uint64_t sequence,
                   std::uint64_t session_id)
    {
        const auto encoded = encode_message(message, sequence, session_id);
        return encoded && send_all(socket, *encoded.value);
    }

    std::optional<DecodedMessage> receive_wire(TestSocket socket)
    {
        std::vector<std::uint8_t> bytes(envelope_size);
        if (!receive_all(socket, bytes))
            return std::nullopt;
        const auto envelope = decode_envelope(bytes);
        if (!envelope)
            return std::nullopt;
        bytes.resize(envelope_size + envelope.value->payload_length);
        if (envelope.value->payload_length > 0 &&
            !receive_all(socket,
                         std::span<std::uint8_t>(bytes).subspan(envelope_size)))
        {
            return std::nullopt;
        }
        auto decoded = decode_message(bytes);
        if (!decoded)
            return std::nullopt;
        return std::move(*decoded.value);
    }

    bool wait_until(const auto& predicate)
    {
        const auto deadline = std::chrono::steady_clock::now() + 2s;
        while (std::chrono::steady_clock::now() < deadline)
        {
            if (predicate())
                return true;
            std::this_thread::sleep_for(1ms);
        }
        return predicate();
    }

    struct ClientSession
    {
        TestSocket socket = invalid_test_socket;
        std::uint64_t id = 0;
    };

    ClientSession
    handshake(RemoteFrameGraphTarget& target,
              const std::string& token,
              std::uint32_t max_payload_bytes = WireLimits::max_payload_bytes)
    {
        ClientSession result;
        result.socket = connect_client(target.status().listening_port);
        if (result.socket == invalid_test_socket)
            return result;
        ClientHello hello;
        hello.authentication_token = token;
        hello.max_payload_bytes = max_payload_bytes;
        hello.max_chunk_bytes =
            std::min(WireLimits::max_chunk_bytes, max_payload_bytes - 1);
        if (!send_wire(result.socket, hello, 1, 0))
        {
            close_test_socket(result.socket);
            result.socket = invalid_test_socket;
            return result;
        }
        const auto response = receive_wire(result.socket);
        if (!response ||
            !std::holds_alternative<TargetHello>(response->message))
        {
            close_test_socket(result.socket);
            result.socket = invalid_test_socket;
            return result;
        }
        result.id = response->envelope.session_id;
        return result;
    }

    void allow_io_and_pump(RemoteFrameGraphTarget& target)
    {
        for (int attempt = 0; attempt < 30; ++attempt)
        {
            std::this_thread::sleep_for(1ms);
            target.pump_render_thread();
        }
    }

    class ProbePass final : public termin::CxxFramePass
    {
    public:
        ProbePass()
        {
            pass_name_set("RemoteProbe");
        }
        std::set<const char*> compute_reads() const override
        {
            return {"input_color"};
        }
        std::set<const char*> compute_writes() const override
        {
            return {"probe_color"};
        }
        std::vector<std::string> get_internal_symbols() const override
        {
            return {"before_probe", "after_probe"};
        }
    };

    class RenderFixture
    {
    public:
        RenderFixture() : manager(topology)
        {
            tc_display_pool_init();
            scene = tc_scene_new();
            target = tc_render_target_new("RemoteTarget");
            tc_render_target_set_scene(target, scene);
            pipeline_handle = tc_pipeline_create("RemotePipeline");
            pipeline.emplace(pipeline_handle);
            pipeline->add_pass((new ProbePass())->tc_pass_ptr());
            tc_render_target_set_pipeline(target, pipeline_handle);
            viewport = tc_viewport_new("RemoteViewport", scene);
            tc_viewport_set_render_target(viewport, target);
            display = tc_display_new("RemoteDisplay", nullptr);
            tc_display_add_viewport(display, viewport);
            manager.add_editor_display(display);
            debugger.emplace(manager);
        }

        ~RenderFixture()
        {
            debugger.reset();
            manager.remove_editor_display(display);
            tc_display_remove_viewport(display, viewport);
            tc_viewport_free(viewport);
            tc_pipeline_destroy(pipeline_handle);
            tc_render_target_free(target);
            tc_display_free(display);
            tc_scene_free(scene);
            tc_display_pool_shutdown();
        }

        termin::RenderTopology topology;
        termin::RenderingManager manager;
        tc_scene_handle scene = TC_SCENE_HANDLE_INVALID;
        tc_render_target_handle target = TC_RENDER_TARGET_HANDLE_INVALID;
        tc_pipeline_handle pipeline_handle = TC_PIPELINE_HANDLE_INVALID;
        std::optional<termin::RenderPipeline> pipeline;
        tc_viewport_handle viewport = TC_VIEWPORT_HANDLE_INVALID;
        tc_display_handle display = TC_DISPLAY_HANDLE_INVALID;
        std::optional<termin::FrameGraphDebugger> debugger;
    };

} // namespace

TEST_CASE(
    "Remote framegraph target validates lifecycle and owner configuration")
{
    RenderFixture fixture;

    TargetServiceConfig forbidden;
    forbidden.bind_address = "0.0.0.0";
    forbidden.authentication_token = "token";
    RemoteFrameGraphTarget rejected(*fixture.debugger, forbidden);
    CHECK_FALSE(rejected.start());

    TargetServiceConfig config;
    config.authentication_token = "target-token";
    RemoteFrameGraphTarget target(*fixture.debugger, config);
    REQUIRE(target.start());
    CHECK(target.start());
    CHECK(target.status().running);
    CHECK(target.status().listening_port != 0);
    CHECK(target.status().graph_revision != 0);
    target.stop();
    target.stop();
    CHECK_FALSE(target.status().running);
    REQUIRE(target.start());
    target.stop();
}

TEST_CASE("Remote framegraph topology smoke covers auth refresh stale "
          "selection and reconnect")
{
    RenderFixture fixture;
    TargetServiceConfig config;
    config.authentication_token = "smoke-token";
    config.platform = "test";
    config.abi = "host";
    config.build_type = "Debug";
    config.build_id = "framegraph-smoke";
    RemoteFrameGraphTarget target(*fixture.debugger, config);
    REQUIRE(target.start());

    TestSocket unauthorized = connect_client(target.status().listening_port);
    REQUIRE(unauthorized != invalid_test_socket);
    ClientHello wrong;
    wrong.authentication_token = "wrong";
    REQUIRE(send_wire(unauthorized, wrong, 1, 0));
    const auto rejection = receive_wire(unauthorized);
    REQUIRE(rejection.has_value());
    CHECK(std::holds_alternative<ErrorEvent>(rejection->message));
    close_test_socket(unauthorized);
    REQUIRE(wait_until([&] { return target.status().rejected_clients == 1; }));

    ClientSession client = handshake(target, "smoke-token");
    REQUIRE(client.socket != invalid_test_socket);
    REQUIRE(client.id != 0);
    REQUIRE(wait_until([&] { return target.status().client_connected; }));

    Command refresh;
    refresh.request_id = 10;
    refresh.kind = CommandKind::refresh_topology;
    REQUIRE(send_wire(client.socket, refresh, 2, client.id));
    allow_io_and_pump(target);
    const auto topology_message = receive_wire(client.socket);
    REQUIRE(topology_message.has_value());
    REQUIRE(
        std::holds_alternative<TopologySnapshot>(topology_message->message));
    const auto topology = std::get<TopologySnapshot>(topology_message->message);
    CHECK_EQ(topology_message->envelope.session_id, client.id);
    REQUIRE_EQ(topology.targets.size(), 1u);
    CHECK_EQ(topology.targets[0].label,
             "RemoteDisplay / RemoteViewport / RemoteTarget");
    REQUIRE_EQ(topology.passes.size(), 1u);
    CHECK_EQ(topology.passes[0].name, "RemoteProbe");
    REQUIRE_EQ(topology.passes[0].reads.size(), 1u);
    CHECK_EQ(topology.passes[0].reads[0], "input_color");
    REQUIRE_EQ(topology.passes[0].writes.size(), 1u);
    CHECK_EQ(topology.passes[0].writes[0], "probe_color");
    CHECK_EQ(topology.passes[0].internal_symbols.size(), 2u);
    REQUIRE_EQ(topology.schedule.size(), 1u);
    CHECK_EQ(topology.schedule[0], topology.passes[0].id);
    CHECK_FALSE(topology.resources.empty());
    const auto refresh_status_message = receive_wire(client.socket);
    REQUIRE(refresh_status_message.has_value());
    REQUIRE(std::holds_alternative<Status>(refresh_status_message->message));
    CHECK(std::get<Status>(refresh_status_message->message).code ==
          StatusCode::completed);

    Command stale;
    stale.request_id = 11;
    stale.kind = CommandKind::select_target;
    stale.target_id = topology.targets[0].id;
    stale.graph_revision = topology.graph_revision + 1;
    REQUIRE(send_wire(client.socket, stale, 3, client.id));
    allow_io_and_pump(target);
    const auto stale_message = receive_wire(client.socket);
    REQUIRE(stale_message.has_value());
    REQUIRE(std::holds_alternative<Status>(stale_message->message));
    CHECK(std::get<Status>(stale_message->message).code ==
          StatusCode::stale_revision);

    Command select = stale;
    select.request_id = 12;
    select.graph_revision = topology.graph_revision;
    REQUIRE(send_wire(client.socket, select, 4, client.id));
    allow_io_and_pump(target);
    const auto selected_topology = receive_wire(client.socket);
    REQUIRE(selected_topology.has_value());
    CHECK(std::holds_alternative<TopologySnapshot>(selected_topology->message));
    const auto select_status = receive_wire(client.socket);
    REQUIRE(select_status.has_value());
    CHECK(std::holds_alternative<Status>(select_status->message));

    Command disconnect;
    disconnect.request_id = 13;
    disconnect.kind = CommandKind::disconnect;
    REQUIRE(send_wire(client.socket, disconnect, 5, client.id));
    const auto disconnect_status = receive_wire(client.socket);
    REQUIRE(disconnect_status.has_value());
    CHECK(std::holds_alternative<Status>(disconnect_status->message));
    close_test_socket(client.socket);
    REQUIRE(wait_until([&] { return !target.status().client_connected; }));

    ClientSession reconnected = handshake(target, "smoke-token");
    REQUIRE(reconnected.socket != invalid_test_socket);
    CHECK(reconnected.id > client.id);
    close_test_socket(reconnected.socket);
    target.stop();
}

TEST_CASE("Remote framegraph exact capture accepts and cancels frame-local work")
{
    RenderFixture fixture;
    TargetServiceConfig config;
    config.authentication_token = "capture-token";
    RemoteFrameGraphTarget target(*fixture.debugger, config);
    REQUIRE(target.start());
    ClientSession client = handshake(target, "capture-token");
    REQUIRE(client.socket != invalid_test_socket);

    Command refresh;
    refresh.request_id = 30;
    refresh.kind = CommandKind::refresh_topology;
    REQUIRE(send_wire(client.socket, refresh, 2, client.id));
    allow_io_and_pump(target);
    const auto topology_message = receive_wire(client.socket);
    REQUIRE(topology_message.has_value());
    REQUIRE(std::holds_alternative<TopologySnapshot>(
        topology_message->message));
    const TopologySnapshot topology =
        std::get<TopologySnapshot>(topology_message->message);
    REQUIRE(receive_wire(client.socket).has_value());
    REQUIRE(topology.selected_target_id != 0);
    REQUIRE_FALSE(topology.resources.empty());

    Command capture;
    capture.request_id = 31;
    capture.kind = CommandKind::capture_snapshot;
    capture.target_id = topology.selected_target_id;
    capture.graph_revision = topology.graph_revision;
    capture.selector_kind = CaptureSelectorKind::resource;
    capture.resource = topology.resources.front();
    capture.encoding = CaptureEncoding::native_pixels;
    REQUIRE(send_wire(client.socket, capture, 3, client.id));
    allow_io_and_pump(target);
    const auto accepted = receive_wire(client.socket);
    REQUIRE(accepted.has_value());
    REQUIRE(std::holds_alternative<Status>(accepted->message));
    CHECK(std::get<Status>(accepted->message).code == StatusCode::accepted);

    Command cancel;
    cancel.request_id = 32;
    cancel.kind = CommandKind::cancel;
    REQUIRE(send_wire(client.socket, cancel, 4, client.id));
    allow_io_and_pump(target);
    const auto cancelled = receive_wire(client.socket);
    REQUIRE(cancelled.has_value());
    REQUIRE(std::holds_alternative<Status>(cancelled->message));
    CHECK(std::get<Status>(cancelled->message).code == StatusCode::cancelled);

    close_test_socket(client.socket);
    target.stop();
}

TEST_CASE("Remote framegraph live preview and burst lifecycle is bounded and idempotent")
{
    RenderFixture fixture;
    TargetServiceConfig config;
    config.authentication_token = "continuous-token";
    RemoteFrameGraphTarget target(*fixture.debugger, config);
    REQUIRE(target.start());
    ClientSession client = handshake(target, "continuous-token");
    REQUIRE(client.socket != invalid_test_socket);

    Command refresh;
    refresh.request_id = 60;
    refresh.kind = CommandKind::refresh_topology;
    REQUIRE(send_wire(client.socket, refresh, 2, client.id));
    allow_io_and_pump(target);
    const auto topology_message = receive_wire(client.socket);
    REQUIRE(topology_message.has_value());
    REQUIRE(std::holds_alternative<TopologySnapshot>(
        topology_message->message));
    const TopologySnapshot topology =
        std::get<TopologySnapshot>(topology_message->message);
    REQUIRE(receive_wire(client.socket).has_value());

    Command stream;
    stream.request_id = 61;
    stream.kind = CommandKind::start_stream;
    stream.target_id = topology.selected_target_id;
    stream.graph_revision = topology.graph_revision;
    stream.selector_kind = CaptureSelectorKind::resource;
    stream.resource = topology.resources.front();
    stream.encoding = CaptureEncoding::rgba8;
    stream.max_preview_millifps = 10'000;
    stream.max_preview_long_edge = 640;
    REQUIRE(send_wire(client.socket, stream, 3, client.id));
    allow_io_and_pump(target);
    const auto stream_status = receive_wire(client.socket);
    REQUIRE(stream_status.has_value());
    REQUIRE(std::holds_alternative<Status>(stream_status->message));
    CHECK(std::get<Status>(stream_status->message).code ==
          StatusCode::accepted);
    CHECK(std::get<Status>(stream_status->message).state ==
          SessionState::streaming);

    Command stop;
    stop.request_id = 62;
    stop.kind = CommandKind::stop_stream;
    stop.target_id = topology.selected_target_id;
    stop.graph_revision = topology.graph_revision;
    REQUIRE(send_wire(client.socket, stop, 4, client.id));
    allow_io_and_pump(target);
    const auto stream_completed = receive_wire(client.socket);
    const auto stop_completed = receive_wire(client.socket);
    REQUIRE(stream_completed.has_value());
    REQUIRE(stop_completed.has_value());
    CHECK(std::get<Status>(stream_completed->message).request_id == 61);
    CHECK(std::get<Status>(stop_completed->message).request_id == 62);

    stop.request_id = 63;
    REQUIRE(send_wire(client.socket, stop, 5, client.id));
    allow_io_and_pump(target);
    const auto repeated_stop = receive_wire(client.socket);
    REQUIRE(repeated_stop.has_value());
    CHECK(std::get<Status>(repeated_stop->message).code ==
          StatusCode::completed);

    Command burst = stream;
    burst.request_id = 64;
    burst.kind = CommandKind::capture_burst;
    burst.encoding = CaptureEncoding::native_pixels;
    burst.max_preview_millifps = 0;
    burst.max_preview_long_edge = 0;
    burst.burst_frames = 4;
    REQUIRE(send_wire(client.socket, burst, 6, client.id));
    allow_io_and_pump(target);
    const auto burst_status = receive_wire(client.socket);
    REQUIRE(burst_status.has_value());
    CHECK(std::get<Status>(burst_status->message).code ==
          StatusCode::accepted);

    Command cancel;
    cancel.request_id = 65;
    cancel.kind = CommandKind::cancel;
    REQUIRE(send_wire(client.socket, cancel, 7, client.id));
    allow_io_and_pump(target);
    const auto burst_cancelled = receive_wire(client.socket);
    const auto cancel_ack = receive_wire(client.socket);
    REQUIRE(burst_cancelled.has_value());
    REQUIRE(cancel_ack.has_value());
    CHECK(std::get<Status>(burst_cancelled->message).request_id == 64);
    CHECK(std::get<Status>(cancel_ack->message).request_id == 65);

    close_test_socket(client.socket);
    target.stop();
}

TEST_CASE("Remote framegraph command queue rejects the newest command")
{
    RenderFixture fixture;
    TargetServiceConfig config;
    config.authentication_token = "queue-token";
    config.command_queue_capacity = 1;
    RemoteFrameGraphTarget target(*fixture.debugger, config);
    REQUIRE(target.start());
    ClientSession client = handshake(target, "queue-token");
    REQUIRE(client.socket != invalid_test_socket);

    Command first;
    first.request_id = 21;
    first.kind = CommandKind::request_status;
    Command rejected = first;
    rejected.request_id = 22;
    REQUIRE(send_wire(client.socket, first, 2, client.id));
    REQUIRE(send_wire(client.socket, rejected, 3, client.id));
    const auto queue_error = receive_wire(client.socket);
    REQUIRE(queue_error.has_value());
    REQUIRE(std::holds_alternative<ErrorEvent>(queue_error->message));
    CHECK_EQ(std::get<ErrorEvent>(queue_error->message).code, 429u);
    REQUIRE(wait_until([&] { return target.status().rejected_commands == 1; }));

    target.pump_render_thread();
    const auto first_status = receive_wire(client.socket);
    REQUIRE(first_status.has_value());
    CHECK(std::holds_alternative<Status>(first_status->message));

    close_test_socket(client.socket);
    target.stop();
}

TEST_CASE("Remote framegraph target honors the client's payload limit")
{
    RenderFixture fixture;
    TargetServiceConfig config;
    config.authentication_token = "small-client-token";
    RemoteFrameGraphTarget target(*fixture.debugger, config);
    REQUIRE(target.start());
    ClientSession client = handshake(target, "small-client-token", 128);
    REQUIRE(client.socket != invalid_test_socket);

    Command refresh;
    refresh.request_id = 28;
    refresh.kind = CommandKind::refresh_topology;
    REQUIRE(send_wire(client.socket, refresh, 2, client.id));
    allow_io_and_pump(target);
    const auto response = receive_wire(client.socket);
    REQUIRE(response.has_value());
    REQUIRE(std::holds_alternative<Status>(response->message));
    CHECK(std::get<Status>(response->message).code ==
          StatusCode::limit_exceeded);

    close_test_socket(client.socket);
    target.stop();
}

TEST_CASE("Remote framegraph outbound queue reports drops after recovery")
{
    RenderFixture fixture;
    TargetServiceConfig config;
    config.authentication_token = "outbound-token";
    config.command_queue_capacity = 32;
    config.outbound_queue_capacity = 1;
    RemoteFrameGraphTarget target(*fixture.debugger, config);
    REQUIRE(target.start());
    ClientSession client = handshake(target, "outbound-token");
    REQUIRE(client.socket != invalid_test_socket);

    for (std::uint64_t index = 0; index < 16; ++index)
    {
        Command fill;
        fill.request_id = 30 + index;
        fill.kind = CommandKind::request_status;
        REQUIRE(send_wire(client.socket, fill, 2 + index, client.id));
    }

    // Hold the I/O thread inside a partial frame after it has accepted the
    // burst. This makes render-to-I/O backpressure deterministic instead of
    // depending on scheduler timing while pump_render_thread() runs.
    Command recovery;
    recovery.request_id = 50;
    recovery.kind = CommandKind::request_status;
    const auto encoded_recovery = encode_message(recovery, 18, client.id);
    REQUIRE(encoded_recovery);
    REQUIRE(send_all(client.socket,
                     std::span<const std::uint8_t>(*encoded_recovery.value)
                         .first(envelope_size)));
    std::this_thread::sleep_for(50ms);
    target.pump_render_thread();
    REQUIRE(wait_until(
        [&] { return target.status().dropped_outbound_messages >= 1; }));
    REQUIRE(send_all(client.socket,
                     std::span<const std::uint8_t>(*encoded_recovery.value)
                         .subspan(envelope_size)));
    allow_io_and_pump(target);

    bool saw_drop = false;
    bool saw_recovery = false;
    for (int attempt = 0; attempt < 18 && !saw_recovery; ++attempt)
    {
        const auto message = receive_wire(client.socket);
        REQUIRE(message.has_value());
        if (std::holds_alternative<DropEvent>(message->message))
        {
            saw_drop = true;
            CHECK(std::get<DropEvent>(message->message).dropped_items >= 1);
        }
        if (std::holds_alternative<Status>(message->message) &&
            std::get<Status>(message->message).request_id == 50)
        {
            saw_recovery = true;
        }
    }
    CHECK(saw_drop);
    CHECK(saw_recovery);

    close_test_socket(client.socket);
    target.stop();
}

GUARD_TEST_MAIN();
