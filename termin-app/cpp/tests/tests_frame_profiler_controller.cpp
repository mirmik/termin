#include "guard_main.h"

#include "termin/editor/frame_profiler_controller.hpp"
#include "termin/editor/frame_profiler_source.hpp"

#include <memory>
#include <tc_profiler.h>
#include <termin/engine/engine_core.hpp>

namespace {

void complete_frame(int index) {
  const tc_profiler_frame_info info{
      1000.0 + index * 16.0, 16.0 + index * 4.0, 16.0,
      index * 4.0,           index == 3 ? 1 : 0,
  };
  tc_profiler_begin_frame_with_info(&info);
  tc_profiler_begin_section("Render");
  tc_profiler_begin_section("Opaque");
  tc_profiler_end_section();
  tc_profiler_end_section();
  tc_profiler_end_frame();
}

termin::gui_native::CommandId
command_id(const termin::gui_native::CommandModel &model,
           const std::string &stable_id) {
  for (const auto &item : model.commands()) {
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
    state->capabilities = static_cast<termin::FrameProfilerCapabilities>(
        termin::FrameProfilerCapability::Clear);
    state->status.connected = true;
    state->status.dropped_frames = 3;
    state->frames = {
        {.frame_number = 10,
         .interval_ms = 16.0,
         .active_ms = 5.0,
         .target_interval_ms = 16.0},
        {.frame_number = 12,
         .interval_ms = 40.0,
         .active_ms = 8.0,
         .target_interval_ms = 16.0},
    };
    state->gaps.push_back({
        termin::FrameProfilerGapKind::TransportDrop,
        11,
        11,
        1,
        "receiver overflow",
    });
  }

  std::uint64_t revision() const override { return state->revision; }
  std::shared_ptr<const termin::FrameProfilerSnapshot> snapshot() override {
    return state;
  }
  bool start_capture() override { return false; }
  bool pause_capture() override { return false; }
  bool set_section_profiling(bool) override { return false; }
  bool clear_capture() override {
    ++clear_requests;
    return true;
  }
  bool set_include_ui(bool) override { return false; }
  void close() override {}

  std::shared_ptr<termin::FrameProfilerSnapshot> state;
  int clear_requests = 0;
};

} // namespace

TEST_CASE(
    "Frame profiler controller keeps capture data and projections native") {
  termin::EngineCore engine;
  termin::FrameProfilerController controller(engine, 3, 1.25);
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
  CHECK(controller.summary_model()->text().find("3 frames") !=
        std::string::npos);
  CHECK(controller.status_model()->text().find("overwritten: 1") !=
        std::string::npos);

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

TEST_CASE(
    "Local profiler source publishes immutable bounded history and gaps") {
  termin::EngineCore engine;
  auto source = termin::make_local_frame_profiler_source(engine, 2);
  const auto empty = source->snapshot();
  CHECK(empty->frames.empty());
  CHECK(termin::has_capability(empty->capabilities,
                               termin::FrameProfilerCapability::IncludeUi));
  REQUIRE(source->start_capture());

  complete_frame(0);
  complete_frame(1);
  complete_frame(2);
  const auto bounded = source->snapshot();
  CHECK(empty->frames.empty());
  REQUIRE_EQ(bounded->frames.size(), 2);
  CHECK(bounded->frames.front().gap_before);
  CHECK_EQ(bounded->status.overwritten_frames, 1);
  REQUIRE_EQ(bounded->gaps.size(), 1);
  CHECK(bounded->gaps.front().kind ==
        termin::FrameProfilerGapKind::CaptureOverwrite);
  CHECK_EQ(bounded->gaps.front().missing_count, 1);
  source->close();
}

TEST_CASE("Controller projects source gaps and disables unsupported controls") {
  auto source = std::make_unique<ContractSource>();
  ContractSource *source_view = source.get();
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
  CHECK(controller.status_model()->text().find("Test phone / session-9") !=
        std::string::npos);
  CHECK(controller.status_model()->text().find("connected") !=
        std::string::npos);
  CHECK(controller.status_model()->text().find("transport drops: 3") !=
        std::string::npos);
  REQUIRE(controller.select_frame(10));
  CHECK_FALSE(controller.follow_latest());

  auto disconnected =
      std::make_shared<termin::FrameProfilerSnapshot>(*source_view->state);
  disconnected->revision = 8;
  disconnected->status.connected = false;
  disconnected->gaps.push_back({termin::FrameProfilerGapKind::Disconnect, 0, 0,
                                0, "transport disconnected"});
  source_view->state = std::move(disconnected);
  REQUIRE(controller.update());
  CHECK_EQ(controller.timeline_model()->samples().size(), 2);
  CHECK_EQ(controller.selected_frame_number(), 10);
  CHECK_FALSE(controller.follow_latest());
  CHECK(controller.status_model()->text().find("disconnected") !=
        std::string::npos);
  CHECK(commands->command(clear).data.enabled);
}

TEST_CASE("Native capture and legacy profiler enable requests compose") {
  termin::EngineCore engine;
  termin::FrameProfilerController controller(engine, 4, 1.25);
  tc_profiler_set_enabled(true);
  controller.start_capture();
  CHECK(controller.summary_model()->text().find("profiling external") !=
        std::string::npos);
  controller.set_profiling(true);
  controller.pause();
  CHECK(tc_profiler_enabled());
  tc_profiler_set_enabled(false);
  CHECK(!tc_profiler_enabled());
  CHECK(!tc_profiler_frame_capture_enabled());
}
