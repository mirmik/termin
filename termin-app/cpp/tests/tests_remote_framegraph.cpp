#include "guard_main.h"

#include "termin/editor/frame_graph_debugger_view.hpp"
#include "termin/editor/remote_frame_graph_debugger_source.hpp"

#include <chrono>
#include <optional>
#include <set>
#include <string>
#include <thread>
#include <vector>

#include <termin/framegraph_remote_target/target_service.hpp>
#include <termin/gui_native/tc_document.hpp>
#include <termin/gui_native/status_bar.hpp>
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
