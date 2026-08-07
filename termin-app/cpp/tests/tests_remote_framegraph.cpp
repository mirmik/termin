#include "guard_main.h"

#include "termin/editor/frame_graph_debugger_view.hpp"
#include "termin/editor/remote_frame_graph_debugger_source.hpp"

#include <chrono>
#include <cstring>
#include <memory>
#include <optional>
#include <span>
#include <set>
#include <string>
#include <thread>
#include <vector>

#include <termin/framegraph_remote_target/target_service.hpp>
#include <termin/gui_native/tc_document.hpp>
#include <termin/gui_native/status_bar.hpp>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/i_render_device.hpp>
#include <termin/render/frame_pass.hpp>
#include <termin/render/rendering_manager.hpp>
#include <termin/render/tc_pass.hpp>

extern "C" {
#include <core/tc_scene.h>
#include <render/tc_display.h>
#include <render/tc_pipeline.h>
#include <render/tc_render_target.h>
#include <render/tc_viewport.h>
}

namespace {

class RemoteProbePass final : public termin::CxxFramePass {
public:
    RemoteProbePass() { pass_name_set("RemoteProbe"); }
    std::set<const char*> compute_reads() const override {
        return {"input_color"};
    }
    std::set<const char*> compute_writes() const override {
        return {"probe_color"};
    }
    std::vector<std::string> get_internal_symbols() const override {
        return {"before_probe", "after_probe"};
    }
};

class RemoteViewFixture {
public:
    RemoteViewFixture() : manager(topology) {
        scene = tc_scene_new();
        render_target = tc_render_target_new("RemoteViewTarget");
        tc_render_target_set_scene(render_target, scene);
        pipeline_handle = tc_pipeline_create("RemoteViewPipeline");
        pipeline.emplace(pipeline_handle);
        pipeline->add_pass((new RemoteProbePass())->tc_pass_ptr());
        tc_render_target_set_pipeline(render_target, pipeline_handle);
        viewport = tc_viewport_new("RemoteViewViewport", scene);
        tc_viewport_set_render_target(viewport, render_target);
        display = tc_display_new("RemoteViewDisplay", nullptr);
        tc_display_add_viewport(display, viewport);
        manager.add_editor_display(display);
        debugger.emplace(manager);
    }

    ~RemoteViewFixture() {
        debugger.reset();
        manager.remove_editor_display(display);
        tc_display_remove_viewport(display, viewport);
        tc_viewport_free(viewport);
        tc_pipeline_destroy(pipeline_handle);
        tc_render_target_free(render_target);
        tc_display_free(display);
        tc_scene_free(scene);
    }

    termin::RenderTopology topology;
    termin::RenderingManager manager;
    tc_scene_handle scene = TC_SCENE_HANDLE_INVALID;
    tc_render_target_handle render_target = TC_RENDER_TARGET_HANDLE_INVALID;
    tc_pipeline_handle pipeline_handle = TC_PIPELINE_HANDLE_INVALID;
    std::optional<termin::RenderPipeline> pipeline;
    tc_viewport_handle viewport = TC_VIEWPORT_HANDLE_INVALID;
    tc_display_handle display = TC_DISPLAY_HANDLE_INVALID;
    std::optional<termin::FrameGraphDebugger> debugger;
};

class DocumentGuard {
public:
    DocumentGuard() : handle(tc_ui_document_create()) {}
    ~DocumentGuard() {
        if (tc_ui_document_is_valid(handle)) tc_ui_document_destroy(handle);
    }
    tc_ui_document_handle handle = tc_ui_document_handle_invalid();
};

class CaptureUploadDevice final : public tgfx::IRenderDevice {
public:
    tgfx::BackendType backend_type() const override {
        return tgfx::BackendType::D3D11;
    }
    tgfx::BackendCapabilities capabilities() const override { return {}; }
    void wait_idle() override {}
    tgfx::BufferHandle create_buffer(const tgfx::BufferDesc&) override { return {}; }
    tgfx::TextureHandle create_texture(const tgfx::TextureDesc& desc) override {
        texture_desc_value = desc;
        return tgfx::TextureHandle{1};
    }
    tgfx::SamplerHandle create_sampler(const tgfx::SamplerDesc&) override { return {}; }
    tgfx::ShaderHandle create_shader(const tgfx::ShaderDesc&) override { return {}; }
    tgfx::PipelineHandle create_pipeline(const tgfx::PipelineDesc&) override { return {}; }
    tgfx::ResourceSetHandle create_bound_resource_set(
        const tgfx::BoundResourceSetDesc&) override { return {}; }
    void destroy(tgfx::BufferHandle) override {}
    void destroy(tgfx::TextureHandle) override { ++destroyed_textures; }
    void destroy(tgfx::SamplerHandle) override {}
    void destroy(tgfx::ShaderHandle) override {}
    void destroy(tgfx::PipelineHandle) override {}
    void destroy(tgfx::ResourceSetHandle) override {}
    void upload_buffer(tgfx::BufferHandle, std::span<const std::uint8_t>,
                       std::uint64_t = 0) override {}
    void upload_texture(tgfx::TextureHandle,
                        std::span<const std::uint8_t> bytes,
                        std::uint32_t = 0) override {
        uploaded.assign(bytes.begin(), bytes.end());
    }
    void upload_texture_region(tgfx::TextureHandle,
                               std::uint32_t, std::uint32_t,
                               std::uint32_t, std::uint32_t,
                               std::span<const std::uint8_t>,
                               std::uint32_t = 0) override {}
    void read_buffer(tgfx::BufferHandle, std::span<std::uint8_t>,
                     std::uint64_t = 0) override {}
    tgfx::TextureDesc texture_desc(tgfx::TextureHandle) const override {
        return texture_desc_value;
    }
    std::unique_ptr<tgfx::ICommandList> create_command_list(
        tgfx::QueueType = tgfx::QueueType::Graphics) override { return {}; }
    void submit(tgfx::ICommandList&) override {}
    void present() override {}
    bool read_texture_depth_float(tgfx::TextureHandle, float* out) override {
        std::memcpy(out, uploaded.data(), uploaded.size());
        return true;
    }

    tgfx::TextureDesc texture_desc_value;
    std::vector<std::uint8_t> uploaded;
    int destroyed_textures = 0;
};

} // namespace

TEST_CASE("RemoteFrameGraphDebuggerSource reconciles revisions and retains stale topology") {
    using namespace termin::framegraph_remote;
    std::vector<Command> commands;
    termin::RemoteFrameGraphDebuggerSource source(
        4, [&commands](const Command& command) {
            commands.push_back(command);
            return true;
        });

    DecodedMessage hello_message;
    hello_message.envelope.session_id = 7;
    hello_message.envelope.sequence = 1;
    TargetHello hello;
    hello.capabilities = static_cast<std::uint64_t>(Capability::topology);
    hello.platform = "linux";
    hello.abi = "x86_64";
    hello_message.message = hello;
    REQUIRE(source.ingest(hello_message));
    CHECK(source.snapshot()->connected);
    CHECK(source.snapshot()->stale);
    REQUIRE(source.refresh());
    REQUIRE_EQ(commands.size(), 1u);
    CHECK(commands[0].kind == CommandKind::refresh_topology);

    DecodedMessage topology_message;
    topology_message.envelope.session_id = 7;
    topology_message.envelope.sequence = 2;
    TopologySnapshot topology;
    topology.graph_revision = 11;
    topology.selected_target_id = 101;
    topology.targets.push_back({101, "Remote Target", true});
    topology.passes.push_back({
        201, 3, "Remote Pass", "Probe", true, false,
        {"input"}, {"output"}, {"before", "after"}});
    topology.schedule.push_back(201);
    topology.resources = {"input", "output"};
    topology.render_stats = "remote stats";
    topology_message.message = topology;
    REQUIRE(source.ingest(topology_message));
    auto snapshot = source.snapshot();
    CHECK_EQ(snapshot->graph_revision, 11u);
    CHECK_FALSE(snapshot->stale);
    REQUIRE_EQ(snapshot->targets.size(), 1u);
    REQUIRE_EQ(snapshot->passes.size(), 1u);
    CHECK(source.select_pass(201));
    CHECK_EQ(source.snapshot()->symbols.size(), 2u);

    DecodedMessage refresh_status_message;
    refresh_status_message.envelope.session_id = 7;
    refresh_status_message.envelope.sequence = 3;
    Status refresh_status;
    refresh_status.request_id = commands[0].request_id;
    refresh_status.graph_revision = 11;
    refresh_status.code = StatusCode::completed;
    refresh_status.detail = "topology refreshed";
    refresh_status_message.message = refresh_status;
    REQUIRE(source.ingest(refresh_status_message));

    REQUIRE(source.select_target(101));
    REQUIRE_EQ(commands.size(), 2u);
    CHECK_EQ(commands.back().graph_revision, 11u);
    DecodedMessage stale_message;
    stale_message.envelope.session_id = 7;
    stale_message.envelope.sequence = 4;
    Status stale;
    stale.request_id = commands.back().request_id;
    stale.graph_revision = 12;
    stale.code = StatusCode::stale_revision;
    stale.detail = "stale graph revision";
    stale_message.message = stale;
    REQUIRE(source.ingest(stale_message));
    CHECK(source.snapshot()->stale);
    REQUIRE(source.refresh());
    REQUIRE_EQ(commands.size(), 3u);
    CHECK(commands.back().kind == CommandKind::refresh_topology);

    DecodedMessage regressed_topology = topology_message;
    regressed_topology.envelope.sequence = 5;
    REQUIRE_FALSE(source.ingest(regressed_topology));
    CHECK_EQ(source.snapshot()->graph_revision, 12u);

    DecodedMessage drop_message;
    drop_message.envelope.session_id = 7;
    drop_message.envelope.sequence = 6;
    drop_message.message = DropEvent{DropKind::receiver, 3, 0, 0};
    REQUIRE(source.ingest(drop_message));
    CHECK_EQ(source.snapshot()->dropped_messages, 3u);
    REQUIRE_EQ(source.snapshot()->gaps.size(), 1u);

    source.transport_disconnected("test disconnect");
    snapshot = source.snapshot();
    CHECK_FALSE(snapshot->connected);
    CHECK(snapshot->stale);
    CHECK_EQ(snapshot->targets.size(), 1u);
    REQUIRE_EQ(snapshot->gaps.size(), 2u);
    CHECK(snapshot->gaps.back().kind ==
          termin::FrameGraphDebuggerGapKind::Disconnect);

    DecodedMessage reconnect = hello_message;
    reconnect.envelope.session_id = 8;
    reconnect.envelope.sequence = 1;
    REQUIRE(source.ingest(reconnect));
    CHECK_EQ(source.snapshot()->session_id, 8u);
    CHECK(source.snapshot()->targets.empty());
}

TEST_CASE("RemoteFrameGraphDebuggerSource assembles exact color HDR and depth blobs") {
    using namespace termin::framegraph_remote;
    std::vector<Command> commands;
    termin::RemoteFrameGraphDebuggerSource source(
        8, [&commands](const Command& command) {
            commands.push_back(command);
            return true;
        });

    std::uint64_t sequence = 1;
    DecodedMessage hello;
    hello.envelope.session_id = 19;
    hello.envelope.sequence = sequence++;
    TargetHello target_hello;
    target_hello.capabilities =
        static_cast<std::uint64_t>(Capability::topology) |
        static_cast<std::uint64_t>(Capability::exact_snapshot);
    hello.message = target_hello;
    REQUIRE(source.ingest(hello));

    DecodedMessage topology_message;
    topology_message.envelope.session_id = 19;
    topology_message.envelope.sequence = sequence++;
    TopologySnapshot topology;
    topology.graph_revision = 4;
    topology.selected_target_id = 2;
    topology.targets.push_back({2, "fixture", true});
    topology.resources.push_back("fixture_resource");
    topology_message.message = topology;
    REQUIRE(source.ingest(topology_message));
    source.set_mode(termin::FrameGraphDebuggerMode::BetweenPasses);

    source.set_selected_resource("fixture_resource");
    REQUIRE_FALSE(commands.empty());
    const std::uint64_t cancelled_request = commands.back().request_id;
    CaptureMetadata partial_metadata;
    partial_metadata.request_id = cancelled_request;
    partial_metadata.graph_revision = 4;
    partial_metadata.blob_id = 90;
    partial_metadata.pixel_format = PixelFormat::rgba8_unorm;
    partial_metadata.width = 2;
    partial_metadata.height = 1;
    partial_metadata.byte_count = 8;
    partial_metadata.chunk_count = 2;
    DecodedMessage partial_message;
    partial_message.envelope.session_id = 19;
    partial_message.envelope.sequence = sequence++;
    partial_message.message = partial_metadata;
    REQUIRE(source.ingest(partial_message));
    source.set_paused(true);
    REQUIRE(commands.back().kind == CommandKind::cancel);
    DecodedMessage cancelled_message;
    cancelled_message.envelope.session_id = 19;
    cancelled_message.envelope.sequence = sequence++;
    Status cancelled_status;
    cancelled_status.request_id = cancelled_request;
    cancelled_status.graph_revision = 4;
    cancelled_status.code = StatusCode::cancelled;
    cancelled_status.detail = "exact capture cancelled";
    cancelled_message.message = cancelled_status;
    REQUIRE(source.ingest(cancelled_message));
    CHECK(source.snapshot()->state != termin::FrameGraphDebuggerState::Error);
    CHECK_EQ(source.snapshot()->capture_info, "Remote capture cancelled");
    source.set_paused(false);

    const auto assemble = [&](PixelFormat format,
                              bool depth,
                              std::uint32_t width,
                              std::uint32_t height,
                              std::vector<std::uint8_t> bytes) {
        source.set_selected_resource("fixture_resource");
        REQUIRE_FALSE(commands.empty());
        const std::uint64_t request_id = commands.back().request_id;
        CaptureMetadata metadata;
        metadata.request_id = request_id;
        metadata.graph_revision = 4;
        metadata.blob_id = request_id + 100;
        metadata.frame_number = static_cast<std::int64_t>(request_id);
        metadata.pixel_format = format;
        metadata.width = width;
        metadata.height = height;
        metadata.is_depth = depth;
        metadata.byte_count = bytes.size();
        metadata.chunk_count = 2;
        DecodedMessage metadata_message;
        metadata_message.envelope.session_id = 19;
        metadata_message.envelope.sequence = sequence++;
        metadata_message.message = metadata;
        REQUIRE(source.ingest(metadata_message));

        const std::size_t first_size = bytes.size() / 2;
        for (std::uint32_t index = 0; index < 2; ++index) {
            const std::size_t offset = index == 0 ? 0 : first_size;
            const std::size_t end = index == 0 ? first_size : bytes.size();
            BlobChunk chunk;
            chunk.blob_id = metadata.blob_id;
            chunk.chunk_index = index;
            chunk.chunk_count = 2;
            chunk.offset = offset;
            chunk.total_bytes = bytes.size();
            chunk.bytes.assign(bytes.begin() + offset, bytes.begin() + end);
            DecodedMessage chunk_message{
                {}, Message{std::in_place_type<BlobChunk>, std::move(chunk)}};
            chunk_message.envelope.session_id = 19;
            chunk_message.envelope.sequence = sequence++;
            REQUIRE(source.ingest(chunk_message));
        }
        const auto capture = source.snapshot()->cpu_capture;
        REQUIRE(capture.has_value());
        CHECK_EQ(capture->width, width);
        CHECK_EQ(capture->height, height);
        CHECK_EQ(capture->is_depth, depth);
        REQUIRE(capture->bytes);
        CHECK(*capture->bytes == bytes);
    };

    assemble(PixelFormat::rgba8_unorm,
             false,
             2,
             1,
             {255, 0, 0, 255, 0, 255, 0, 255});
    std::vector<float> hdr_values = {2.0F, 0.5F, -1.0F, 1.0F};
    std::vector<std::uint8_t> hdr_bytes(sizeof(float) * hdr_values.size());
    std::memcpy(hdr_bytes.data(), hdr_values.data(), hdr_bytes.size());
    assemble(PixelFormat::rgba32_float, false, 1, 1, hdr_bytes);
    CHECK(source.analyze_hdr().find("HDR pixels:</b> 1") !=
          std::string::npos);
    std::vector<float> depth_values = {0.25F, 0.75F};
    std::vector<std::uint8_t> depth_bytes(
        sizeof(float) * depth_values.size());
    std::memcpy(depth_bytes.data(), depth_values.data(), depth_bytes.size());
    assemble(PixelFormat::depth32_float, true, 2, 1, depth_bytes);
    CaptureUploadDevice device;
    int depth_width = 0;
    int depth_height = 0;
    const auto normalized = source.read_depth_normalized(
        device, &depth_width, &depth_height);
    CHECK_EQ(depth_width, 2);
    CHECK_EQ(depth_height, 1);
    REQUIRE_EQ(normalized.size(), 2u);
    CHECK(device.uploaded == depth_bytes);
    depth_values = {0.1F, 0.9F};
    std::memcpy(depth_bytes.data(), depth_values.data(), depth_bytes.size());
    assemble(PixelFormat::depth32_float, true, 2, 1, depth_bytes);
    const auto repeated = source.read_depth_normalized(
        device, &depth_width, &depth_height);
    REQUIRE_EQ(repeated.size(), 2u);
    CHECK_EQ(device.destroyed_textures, 1);
    source.disconnect();
    CHECK_EQ(device.destroyed_textures, 2);
    CHECK_FALSE(source.snapshot()->cpu_capture.has_value());
    CHECK_FALSE(source.snapshot()->main_image.available);
}

TEST_CASE("RemoteFrameGraphDebuggerSource tracks live preview and burst gaps") {
    using namespace termin::framegraph_remote;
    std::vector<Command> commands;
    termin::RemoteFrameGraphDebuggerSource source(
        8, [&commands](const Command& command) {
            commands.push_back(command);
            return true;
        });
    std::uint64_t sequence = 1;
    const auto ingest = [&](Message message) {
        DecodedMessage decoded;
        decoded.envelope.session_id = 23;
        decoded.envelope.sequence = sequence++;
        decoded.message = std::move(message);
        return source.ingest(decoded);
    };

    TargetHello hello;
    hello.capabilities =
        static_cast<std::uint64_t>(Capability::topology) |
        static_cast<std::uint64_t>(Capability::exact_snapshot) |
        static_cast<std::uint64_t>(Capability::live_preview) |
        static_cast<std::uint64_t>(Capability::burst_capture);
    REQUIRE(ingest(hello));
    TopologySnapshot topology;
    topology.graph_revision = 8;
    topology.selected_target_id = 3;
    topology.targets.push_back({3, "stream fixture", true});
    topology.resources.push_back("color");
    REQUIRE(ingest(topology));
    source.set_mode(termin::FrameGraphDebuggerMode::BetweenPasses);
    source.set_selected_resource("color");
    REQUIRE_FALSE(commands.empty());
    const std::uint64_t exact_request = commands.back().request_id;
    REQUIRE(ingest(Status{exact_request, 8, SessionState::idle,
                          StatusCode::cancelled, 0, 0, 0, 0,
                          "superseded by live preview"}));

    REQUIRE(source.start_live_preview(12'000, 720));
    REQUIRE(commands.back().kind == CommandKind::start_stream);
    CHECK_EQ(commands.back().max_preview_millifps, 12'000u);
    CHECK_EQ(commands.back().max_preview_long_edge, 720u);
    const std::uint64_t stream_request = commands.back().request_id;
    REQUIRE(ingest(Status{stream_request, 8, SessionState::streaming,
                          StatusCode::accepted, 0, 0, 0, 0,
                          "live preview started"}));
    CHECK(source.snapshot()->live_preview_active);

    const auto frame = [&](std::uint64_t blob_id,
                           std::int64_t frame_number,
                           CaptureKind kind,
                           std::uint16_t burst_index,
                           std::uint16_t burst_count,
                           std::uint64_t request_id) {
        CaptureMetadata metadata;
        metadata.request_id = request_id;
        metadata.graph_revision = 8;
        metadata.blob_id = blob_id;
        metadata.frame_number = frame_number;
        metadata.kind = kind;
        metadata.encoding = kind == CaptureKind::preview
            ? CaptureEncoding::rgba8 : CaptureEncoding::native_pixels;
        metadata.pixel_format = PixelFormat::rgba8_unorm;
        metadata.width = 1;
        metadata.height = 1;
        metadata.exact = kind != CaptureKind::preview;
        metadata.byte_count = 4;
        metadata.chunk_count = 1;
        metadata.burst_index = burst_index;
        metadata.burst_count = burst_count;
        REQUIRE(ingest(metadata));
        BlobChunk chunk;
        chunk.blob_id = blob_id;
        chunk.chunk_count = 1;
        chunk.total_bytes = 4;
        chunk.bytes = {static_cast<std::uint8_t>(frame_number), 2, 3, 255};
        REQUIRE(ingest(std::move(chunk)));
    };

    frame(101, 10, CaptureKind::preview, 0, 0, stream_request);
    frame(102, 11, CaptureKind::preview, 0, 0, stream_request);
    REQUIRE(source.snapshot()->cpu_capture.has_value());
    CHECK_EQ(source.snapshot()->cpu_capture->generation, 102u);
    CHECK_EQ(source.snapshot()->cpu_capture->frame_number, 11);
    CHECK_FALSE(source.snapshot()->cpu_capture->exact);

    REQUIRE(source.stop_live_preview());
    REQUIRE(commands.back().kind == CommandKind::stop_stream);
    const std::uint64_t stop_request = commands.back().request_id;
    REQUIRE(ingest(Status{stream_request, 8, SessionState::idle,
                          StatusCode::completed, 0, 2, 0, 0,
                          "live preview stopped"}));
    REQUIRE(ingest(Status{stop_request, 8, SessionState::idle,
                          StatusCode::completed, 0, 2, 0, 0,
                          "stop processed"}));
    CHECK_FALSE(source.snapshot()->live_preview_active);

    REQUIRE(source.capture_burst(3));
    REQUIRE(commands.back().kind == CommandKind::capture_burst);
    const std::uint64_t burst_request = commands.back().request_id;
    REQUIRE(ingest(Status{burst_request, 8, SessionState::waiting_capture,
                          StatusCode::accepted, 0, 2, 0, 0,
                          "burst accepted"}));
    frame(201, 20, CaptureKind::burst, 0, 3, burst_request);
    frame(203, 22, CaptureKind::burst, 2, 3, burst_request);
    REQUIRE(ingest(Status{burst_request, 8, SessionState::idle,
                          StatusCode::completed, 0, 4, 1, 0,
                          "burst completed"}));
    REQUIRE(source.snapshot()->cpu_capture.has_value());
    CHECK_EQ(source.snapshot()->cpu_capture->burst_index, 2u);
    CHECK_EQ(source.snapshot()->cpu_capture->burst_count, 3u);
    CHECK(source.snapshot()->dropped_messages >= 1);
    CHECK_FALSE(source.snapshot()->gaps.empty());
}

TEST_CASE("FrameGraphDebuggerView switches local remote stale and local in one tree") {
    using namespace std::chrono_literals;
    RemoteViewFixture fixture;
    termin::framegraph_remote_target::TargetServiceConfig target_config;
    target_config.authentication_token = "view-session-token";
    target_config.platform = "test";
    target_config.abi = "host";
    termin::framegraph_remote_target::RemoteFrameGraphTarget target_service(
        *fixture.debugger, target_config);
    REQUIRE(target_service.start());

    DocumentGuard document;
    termin::FrameGraphDebuggerView view(
        termin::gui_native::TcDocument(document.handle), *fixture.debugger);
    REQUIRE(view.activate());
    const tc_widget_handle root = view.root_handle();
    REQUIRE(view.connect_remote(
        target_service.status().listening_port, "wrong-session-token"));
    bool auth_failure_visible = false;
    for (int attempt = 0; attempt < 200; ++attempt) {
        view.update();
        const auto remote = view.source_snapshot();
        if (!remote->connected &&
            remote->status_detail.find("authentication token is invalid") !=
                std::string::npos) {
            auth_failure_visible = true;
            break;
        }
        std::this_thread::sleep_for(5ms);
    }
    REQUIRE(auth_failure_visible);
    CHECK(target_service.status().rejected_clients >= 1);

    REQUIRE(view.connect_remote(
        target_service.status().listening_port, "view-session-token"));
    CHECK(view.using_remote());
    bool received_topology = false;
    for (int attempt = 0; attempt < 400; ++attempt) {
        target_service.pump_render_thread();
        view.update();
        const auto remote = view.source_snapshot();
        if (remote->connected && !remote->stale &&
            !remote->targets.empty() && !remote->passes.empty()) {
            received_topology = true;
            break;
        }
        std::this_thread::sleep_for(5ms);
    }
    REQUIRE(received_topology);
    CHECK_EQ(tc_ui_document_root_count(document.handle), 1u);
    CHECK(tc_widget_handle_eq(view.root_handle(), root));
    CHECK(view.source_snapshot()->source_kind ==
          termin::FrameGraphDebuggerSourceKind::Remote);
    CHECK(view.state_status()->text().find("Remote /") != std::string::npos);

    REQUIRE_FALSE(view.source_snapshot()->resources.empty());
    REQUIRE(view.show_resource(view.source_snapshot()->resources.front()));
    REQUIRE(view.start_live_preview(5'000, 320));
    bool preview_started = false;
    for (int attempt = 0; attempt < 200; ++attempt) {
        target_service.pump_render_thread();
        view.update();
        if (view.source_snapshot()->live_preview_active) {
            preview_started = true;
            break;
        }
        std::this_thread::sleep_for(5ms);
    }
    REQUIRE(preview_started);
    CHECK(view.state_status()->text().find("[LIVE]") != std::string::npos);
    REQUIRE(view.stop_live_preview());
    bool preview_stopped = false;
    for (int attempt = 0; attempt < 200; ++attempt) {
        target_service.pump_render_thread();
        view.update();
        if (!view.source_snapshot()->live_preview_active) {
            preview_stopped = true;
            break;
        }
        std::this_thread::sleep_for(5ms);
    }
    REQUIRE(preview_stopped);

    view.disconnect_remote();
    CHECK(view.source_snapshot()->stale);
    CHECK_FALSE(view.source_snapshot()->targets.empty());
    CHECK(view.state_status()->text().find("[STALE]") != std::string::npos);

    REQUIRE(view.use_local());
    CHECK_FALSE(view.using_remote());
    CHECK(view.source_snapshot()->source_kind ==
          termin::FrameGraphDebuggerSourceKind::Local);
    CHECK_EQ(tc_ui_document_root_count(document.handle), 1u);
    CHECK(tc_widget_handle_eq(view.root_handle(), root));

    view.close();
    target_service.stop();
}
