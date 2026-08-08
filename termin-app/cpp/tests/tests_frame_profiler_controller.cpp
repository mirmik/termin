#include "guard_main.h"

#include <termin/frame_profiler/frame_profiler_controller.hpp>
#include <termin/frame_profiler/frame_profiler_source.hpp>
#include <termin/frame_profiler/remote_frame_profiler_source.hpp>

#include <memory>
#include <tc_profiler.h>
#include <termin/engine/engine_core.hpp>
#include <termin/profiler_remote/target_service.hpp>
#include <thread>

namespace {

    bool wait_until(const auto& predicate) {
        const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
        while (std::chrono::steady_clock::now() < deadline) {
            if (predicate())
                return true;
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
        return predicate();
    }

    termin::profiler_remote::DecodedMessage
    remote_message(std::uint64_t sequence, std::uint64_t session, termin::profiler_remote::Message message) {
        return {{termin::profiler_remote::protocol_major,
                 termin::profiler_remote::protocol_minor,
                 termin::profiler_remote::message_type(message),
                 0,
                 0,
                 sequence,
                 session},
                std::move(message)};
    }

    void complete_frame(int index) {
        const tc_profiler_frame_info info{
            1000.0 + index * 16.0,
            16.0 + index * 4.0,
            16.0,
            index * 4.0,
            index == 3 ? 1 : 0,
        };
        tc_profiler_begin_frame_with_info(&info);
        tc_profiler_begin_section("Render");
        tc_profiler_begin_section("Opaque");
        tc_profiler_end_section();
        tc_profiler_end_section();
        tc_profiler_end_frame();
    }

    termin::gui_native::CommandId command_id(const termin::gui_native::CommandModel& model,
                                             const std::string& stable_id) {
        for (const auto& item : model.commands()) {
            if (item.data.stable_id == stable_id)
                return item.id;
        }
        return termin::gui_native::kInvalidCommandId;
    }

    class ContractSource final : public termin::IFrameProfilerSource {
    public:
        ContractSource() {
            state = std::make_shared<termin::FrameProfilerSnapshot>();
            state->revision = 7;
            state->capacity = 2;
            state->identity = {"remote:test", "session-9", "Test phone"};
            state->capabilities =
                static_cast<termin::FrameProfilerCapabilities>(termin::FrameProfilerCapability::Clear);
            state->status.connected = true;
            state->status.dropped_frames = 3;
            state->frames = {
                {.frame_number = 10, .interval_ms = 16.0, .active_ms = 5.0, .target_interval_ms = 16.0},
                {.frame_number = 12, .interval_ms = 40.0, .active_ms = 8.0, .target_interval_ms = 16.0},
            };
            state->gaps.push_back({
                termin::FrameProfilerGapKind::TransportDrop,
                11,
                11,
                1,
                "receiver overflow",
            });
        }

        std::uint64_t revision() const override {
            return state->revision;
        }
        std::shared_ptr<const termin::FrameProfilerSnapshot> snapshot() override {
            return state;
        }
        bool start_capture() override {
            return false;
        }
        bool pause_capture() override {
            return false;
        }
        bool set_section_profiling(bool) override {
            return false;
        }
        bool clear_capture() override {
            ++clear_requests;
            return true;
        }
        bool set_include_ui(bool) override {
            return false;
        }
        void close() override {}

        std::shared_ptr<termin::FrameProfilerSnapshot> state;
        int clear_requests = 0;
    };

} // namespace

TEST_CASE("Frame profiler controller keeps capture data and projections native") {
    termin::EngineCore engine;
    termin::FrameProfilerController controller(termin::make_local_frame_profiler_source(engine, 3), 1.25);
    controller.start_capture();
    CHECK(controller.capturing());
    CHECK(tc_profiler_frame_capture_enabled());
    CHECK(!controller.profiling());
    CHECK(!tc_profiler_enabled());

    for (int index = 0; index < 4; ++index) {
        if (index == 1)
            controller.set_profiling(true);
        complete_frame(index);
    }

    CHECK(controller.update());
    CHECK(controller.timeline_model()->samples().size() == 3);
    CHECK(controller.section_model()->size() == 2);
    CHECK(controller.selected_frame_number() >= 0);
    CHECK(controller.summary_model()->text().find("3 frames") != std::string::npos);
    CHECK(controller.status_model()->text().find("overwritten: 1") != std::string::npos);

    const int selected = controller.selected_frame_number();
    CHECK(controller.select_frame(selected - 1));
    CHECK(!controller.follow_latest());
    controller.clear();
    CHECK(controller.timeline_model()->samples().empty());
    CHECK(controller.section_model()->empty());
    CHECK(controller.capturing());

    controller.close();
    CHECK(!tc_profiler_enabled());
    CHECK(!tc_profiler_frame_capture_enabled());
}

TEST_CASE("Local profiler source publishes immutable bounded history and gaps") {
    termin::EngineCore engine;
    auto source = termin::make_local_frame_profiler_source(engine, 2);
    const auto empty = source->snapshot();
    CHECK(empty->frames.empty());
    CHECK(termin::has_capability(empty->capabilities, termin::FrameProfilerCapability::IncludeUi));
    REQUIRE(source->start_capture());

    complete_frame(0);
    complete_frame(1);
    REQUIRE(tc_profiler_publish_gpu_frame_timing(tc_profiler_frame_count() - 1, 2.25));
    complete_frame(2);
    const auto bounded = source->snapshot();
    CHECK(empty->frames.empty());
    REQUIRE_EQ(bounded->frames.size(), 2);
    CHECK(bounded->frames.front().gap_before);
    CHECK_EQ(bounded->status.overwritten_frames, 1);
    REQUIRE_EQ(bounded->gaps.size(), 1);
    CHECK(bounded->gaps.front().kind == termin::FrameProfilerGapKind::CaptureOverwrite);
    CHECK_EQ(bounded->gaps.front().missing_count, 1);
    const auto* gpu_frame = bounded->find(tc_profiler_frame_count() - 2);
    REQUIRE(gpu_frame != nullptr);
    CHECK(gpu_frame->has_gpu_duration);
    CHECK(gpu_frame->gpu_duration_ms == 2.25);
    source->close();
}

TEST_CASE("Controller projects source gaps and disables unsupported controls") {
    auto source = std::make_unique<ContractSource>();
    ContractSource* source_view = source.get();
    termin::FrameProfilerController controller(std::move(source), 1.25);
    const auto commands = controller.command_model();
    const auto capture = command_id(*commands, "capture");
    const auto clear = command_id(*commands, "clear");
    const auto include_ui = command_id(*commands, "include-ui");
    REQUIRE(capture != termin::gui_native::kInvalidCommandId);
    REQUIRE(clear != termin::gui_native::kInvalidCommandId);
    REQUIRE(include_ui != termin::gui_native::kInvalidCommandId);
    CHECK_FALSE(commands->command(capture).data.enabled);
    CHECK(commands->command(clear).data.enabled);
    CHECK_FALSE(commands->command(include_ui).data.enabled);
    CHECK_FALSE(controller.activate(capture));
    CHECK(controller.activate(clear));
    CHECK_EQ(source_view->clear_requests, 1);

    REQUIRE_EQ(controller.timeline_model()->samples().size(), 2);
    CHECK_FALSE(controller.timeline_model()->samples()[0].gap_before);
    CHECK(controller.timeline_model()->samples()[1].gap_before);
    CHECK(controller.timeline_model()->samples()[1].hitch);
    CHECK(controller.status_model()->text().find("Test phone / session-9") != std::string::npos);
    CHECK(controller.status_model()->text().find("connected") != std::string::npos);
    CHECK(controller.status_model()->text().find("transport drops: 3") != std::string::npos);
    REQUIRE(controller.select_frame(10));
    CHECK_FALSE(controller.follow_latest());

    auto disconnected = std::make_shared<termin::FrameProfilerSnapshot>(*source_view->state);
    disconnected->revision = 8;
    disconnected->status.connected = false;
    disconnected->gaps.push_back({termin::FrameProfilerGapKind::Disconnect, 0, 0, 0, "transport disconnected"});
    source_view->state = std::move(disconnected);
    REQUIRE(controller.update());
    CHECK_EQ(controller.timeline_model()->samples().size(), 2);
    CHECK_EQ(controller.selected_frame_number(), 10);
    CHECK_FALSE(controller.follow_latest());
    CHECK(controller.status_model()->text().find("disconnected") != std::string::npos);
    CHECK(commands->command(clear).data.enabled);
}

TEST_CASE("Recorded remote protocol replay projects frames and acknowledged "
          "controls") {
    using namespace termin::profiler_remote;
    std::vector<Control> sent_controls;
    auto source = std::make_unique<termin::RemoteFrameProfilerSource>(2, [&sent_controls](const Control& control) {
        sent_controls.push_back(control);
        return true;
    });
    auto* source_view = source.get();

    TargetHello hello;
    hello.capabilities = static_cast<std::uint64_t>(Capability::cadence_capture) |
                         static_cast<std::uint64_t>(Capability::hierarchical_sections) |
                         static_cast<std::uint64_t>(Capability::clear_capture);
    hello.process_id = 42;
    hello.platform = "Android";
    hello.abi = "arm64-v8a";
    hello.build_type = "Profile";
    REQUIRE(source_view->ingest(remote_message(1, 77, hello)));
    REQUIRE(source_view->ingest(remote_message(2, 77, DictionaryAdd{{{1, "Host Frame"}, {2, "Present"}}})));

    FrameBatch first;
    first.frames = {
        {.frame_number = 100,
         .interval_ms = 16.0,
         .active_ms = 6.0,
         .target_interval_ms = 16.0,
         .sections_profiled = true,
         .sections = {{1, 5.0, 2.0, 1, -1, 1, -1}, {2, 2.0, 0.0, 1, 0, -1, -1}}},
        {.frame_number = 101, .interval_ms = 17.0, .active_ms = 7.0, .target_interval_ms = 16.0},
    };
    REQUIRE(source_view->ingest(remote_message(3, 77, first)));
    REQUIRE(source_view->ingest(remote_message(4, 77, DropEvent{DropKind::producer_queue, 1, 2, 3})));
    FrameBatch latest;
    latest.frames = {{.frame_number = 104, .interval_ms = 40.0, .active_ms = 8.0, .target_interval_ms = 16.0}};
    REQUIRE(source_view->ingest(remote_message(5, 77, latest)));

    termin::FrameProfilerController controller(std::move(source), 1.25);
    REQUIRE_EQ(controller.timeline_model()->samples().size(), 2);
    CHECK_EQ(controller.timeline_model()->samples()[0].stable_id, 101);
    CHECK_EQ(controller.timeline_model()->samples()[1].stable_id, 104);
    CHECK(controller.timeline_model()->samples()[1].gap_before);
    CHECK(controller.timeline_model()->samples()[1].hitch);
    CHECK(controller.status_model()->text().find("Android / arm64-v8a") != std::string::npos);
    CHECK(controller.status_model()->text().find("transport drops: 3") != std::string::npos);

    controller.start_capture();
    REQUIRE_EQ(sent_controls.size(), 1);
    CHECK(sent_controls[0].kind == ControlKind::start_capture);
    CHECK_FALSE(controller.capturing());
    REQUIRE(source_view->ingest(
        remote_message(6, 77, Status{sent_controls[0].request_id, true, false, 3, 2, 0, 0, "capture started"})));
    REQUIRE(controller.update());
    CHECK(controller.capturing());

    const auto revision = source_view->revision();
    FrameBatch malformed;
    malformed.frames = {{.frame_number = 105, .sections_profiled = true, .sections = {{999, 1.0, 0.0, 1, -1, -1, -1}}}};
    CHECK_FALSE(source_view->ingest(remote_message(7, 77, malformed)));
    CHECK_EQ(source_view->revision(), revision);

    source_view->transport_disconnected("recorded disconnect");
    const auto disconnected = source_view->snapshot();
    REQUIRE_EQ(disconnected->frames.size(), 2);
    CHECK_FALSE(disconnected->status.connected);
    CHECK(disconnected->gaps.back().kind == termin::FrameProfilerGapKind::Disconnect);

    REQUIRE(source_view->ingest(remote_message(1, 78, hello)));
    const auto reconnected = source_view->snapshot();
    CHECK(reconnected->frames.empty());
    CHECK_EQ(reconnected->identity.session_id, "78");
    CHECK(reconnected->status.connected);
}

TEST_CASE("Live remote source controls target and inspects an exact frame") {
    using namespace termin::profiler_remote;
    tc_profiler_set_enabled(false);
    tc_profiler_clear_history();

    TargetServiceConfig target_config;
    target_config.authentication_token = "live-session-token";
    target_config.platform = "Desktop test";
    target_config.abi = "host";
    target_config.build_type = "Tests";
    target_config.process_id = 1155;
    target_config.capture_capacity = 8;
    target_config.frames_per_batch = 1;
    RemoteProfilerTarget target(std::move(target_config));
    REQUIRE(target.start());

    auto source = std::make_unique<termin::RemoteFrameProfilerSource>(8);
    auto* source_view = source.get();
    ClientConfig client_config;
    client_config.port = target.status().listening_port;
    client_config.authentication_token = "live-session-token";
    client_config.reconnect = false;
    REQUIRE(source_view->connect(std::move(client_config)));
    REQUIRE(wait_until([&] { return source_view->snapshot()->status.connected; }));

    REQUIRE(source_view->start_capture());
    REQUIRE(source_view->set_section_profiling(true));
    REQUIRE(wait_until([&] {
        target.pump_frame_thread();
        const auto snapshot = source_view->snapshot();
        return snapshot->status.capturing && snapshot->status.profiling_sections;
    }));

    complete_frame(20);
    REQUIRE(wait_until([&] {
        target.pump_frame_thread();
        return !source_view->snapshot()->frames.empty();
    }));
    const auto exact_frame = source_view->snapshot()->frames.back().frame_number;

    termin::FrameProfilerController controller(std::move(source), 1.25);
    REQUIRE_EQ(controller.timeline_model()->samples().size(), 1);
    CHECK_EQ(controller.timeline_model()->samples().front().stable_id, exact_frame);
    REQUIRE(controller.select_frame(exact_frame));
    CHECK_EQ(controller.section_model()->size(), 2);
    CHECK(controller.detail_model()->text().find("Frame " + std::to_string(exact_frame)) != std::string::npos);

    controller.pause();
    REQUIRE(wait_until([&] {
        target.pump_frame_thread();
        controller.update();
        return !controller.capturing();
    }));
    controller.close();
    target.stop();
    tc_profiler_set_enabled(false);
    tc_profiler_clear_history();
}

TEST_CASE("Native capture and legacy profiler enable requests compose") {
    termin::EngineCore engine;
    termin::FrameProfilerController controller(termin::make_local_frame_profiler_source(engine, 4), 1.25);
    tc_profiler_set_enabled(true);
    controller.start_capture();
    CHECK(controller.summary_model()->text().find("profiling external") != std::string::npos);
    controller.set_profiling(true);
    controller.pause();
    CHECK(tc_profiler_enabled());
    tc_profiler_set_enabled(false);
    CHECK(!tc_profiler_enabled());
    CHECK(!tc_profiler_frame_capture_enabled());
}
