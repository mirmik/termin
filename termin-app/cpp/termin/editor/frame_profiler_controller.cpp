#include "termin/editor/frame_profiler_controller.hpp"
#include "termin/editor/remote_frame_profiler_source.hpp"

#include <algorithm>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include <termin/engine/engine_core.hpp>

namespace termin {

namespace {

gui_native::CommandData command(std::string id, std::string label,
                                bool checkable = false, bool checked = false) {
  gui_native::CommandData data;
  data.stable_id = std::move(id);
  data.label = std::move(label);
  data.checkable = checkable;
  data.checked = checked;
  return data;
}

gui_native::CommandData separator(std::string id) {
  auto data = command(std::move(id), "");
  data.kind = gui_native::CommandKind::Separator;
  return data;
}

std::string section_id(int index) { return "section-" + std::to_string(index); }

std::string milliseconds(double value, int precision = 3) {
  std::ostringstream stream;
  stream << std::fixed << std::setprecision(precision) << value;
  return stream.str();
}

bool frame_is_hitch(const FrameProfilerFrame &frame, double hitch_ratio) {
  return frame.missed_intervals > 0 ||
         (frame.target_interval_ms > 0.0 &&
          frame.interval_ms > frame.target_interval_ms * hitch_ratio);
}

bool has_gap_before(const FrameProfilerSnapshot &snapshot,
                    const FrameProfilerFrame &frame) {
  if (frame.gap_before)
    return true;
  return std::any_of(snapshot.gaps.begin(), snapshot.gaps.end(),
                     [&frame](const FrameProfilerGap &gap) {
                       return gap.missing_count > 0 &&
                              gap.last_missing_frame == frame.frame_number - 1;
                     });
}

double percentile(std::vector<double> values, double quantile) {
  if (values.empty())
    return 0.0;
  std::sort(values.begin(), values.end());
  const double position = static_cast<double>(values.size() - 1) * quantile;
  const auto lower = static_cast<std::size_t>(position);
  const auto upper = std::min(lower + 1, values.size() - 1);
  const double fraction = position - static_cast<double>(lower);
  return values[lower] * (1.0 - fraction) + values[upper] * fraction;
}

struct FrameStatistics {
  std::size_t frame_count = 0;
  std::size_t hitch_count = 0;
  double interval_p50_ms = 0.0;
  double interval_p95_ms = 0.0;
  double interval_p99_ms = 0.0;
  double max_interval_ms = 0.0;
};

FrameStatistics statistics(const FrameProfilerSnapshot &snapshot,
                           double hitch_ratio) {
  FrameStatistics result;
  result.frame_count = snapshot.frames.size();
  std::vector<double> intervals;
  intervals.reserve(snapshot.frames.size());
  for (const auto &frame : snapshot.frames) {
    if (frame.interval_ms > 0.0)
      intervals.push_back(frame.interval_ms);
    result.max_interval_ms =
        std::max(result.max_interval_ms, frame.interval_ms);
    if (frame_is_hitch(frame, hitch_ratio))
      ++result.hitch_count;
  }
  result.interval_p50_ms = percentile(intervals, 0.50);
  result.interval_p95_ms = percentile(intervals, 0.95);
  result.interval_p99_ms = percentile(std::move(intervals), 0.99);
  return result;
}

} // namespace

FrameProfilerController::FrameProfilerController(EngineCore &engine,
                                                 int capacity,
                                                 double hitch_ratio)
    : FrameProfilerController(
          make_local_frame_profiler_source(engine, capacity), hitch_ratio) {}

FrameProfilerController::FrameProfilerController(
    std::unique_ptr<IFrameProfilerSource> source, double hitch_ratio)
    : source_(std::move(source)), hitch_ratio_(hitch_ratio),
      commands_(std::make_shared<gui_native::CommandModel>()),
      timeline_(std::make_shared<gui_native::FrameTimelineModel>()),
      sections_(std::make_shared<gui_native::TreeTableModel>()),
      summary_(std::make_shared<gui_native::RichTextModel>()),
      detail_(std::make_shared<gui_native::RichTextModel>()),
      status_(std::make_shared<gui_native::RichTextModel>()) {
  if (!source_)
    throw std::invalid_argument("profiler source must not be null");
  if (hitch_ratio <= 1.0)
    throw std::invalid_argument("profiler hitch ratio must exceed one");
  snapshot_ = source_->snapshot();
  if (!snapshot_)
    throw std::runtime_error("profiler source returned no snapshot");
  observed_source_id_ = snapshot_->identity.source_id;
  observed_session_id_ = snapshot_->identity.session_id;

  capture_command_ = commands_->append(command("capture", "Capture", true));
  profiling_command_ =
      commands_->append(command("profiling", "Profiling", true));
  clear_command_ = commands_->append(command("clear", "Clear"));
  commands_->append(separator("separator-1"));
  follow_command_ = commands_->append(command("follow", "Follow", true, true));
  include_ui_command_ = commands_->append(
      command("include-ui", "Include UI", true, snapshot_->status.include_ui));
  commands_->append(separator("separator-2"));
  previous_hitch_command_ =
      commands_->append(command("previous-hitch", "Previous Hitch"));
  next_hitch_command_ = commands_->append(command("next-hitch", "Next Hitch"));
  update_capability_commands();
  refresh_models();
}

FrameProfilerController::~FrameProfilerController() { close(); }

std::shared_ptr<gui_native::CommandModel>
FrameProfilerController::command_model() const {
  return commands_;
}
std::shared_ptr<gui_native::FrameTimelineModel>
FrameProfilerController::timeline_model() const {
  return timeline_;
}
std::shared_ptr<gui_native::TreeTableModel>
FrameProfilerController::section_model() const {
  return sections_;
}
std::shared_ptr<gui_native::RichTextModel>
FrameProfilerController::summary_model() const {
  return summary_;
}
std::shared_ptr<gui_native::RichTextModel>
FrameProfilerController::detail_model() const {
  return detail_;
}
std::shared_ptr<gui_native::RichTextModel>
FrameProfilerController::status_model() const {
  return status_;
}

int FrameProfilerController::capacity() const {
  return snapshot_ ? static_cast<int>(snapshot_->capacity) : 0;
}

bool FrameProfilerController::capturing() const {
  return snapshot_ && snapshot_->status.capturing;
}

bool FrameProfilerController::profiling() const {
  return snapshot_ && snapshot_->status.profiling_sections;
}

void FrameProfilerController::start_capture() {
  if (capturing() || !source_->start_capture())
    return;
  snapshot_ = source_->snapshot();
  update_capture_command();
  refresh_summary();
}

void FrameProfilerController::pause() {
  if (!capturing() || !source_->pause_capture())
    return;
  snapshot_ = source_->snapshot();
  update_capture_command();
  refresh_summary();
}

void FrameProfilerController::set_profiling(bool enabled) {
  if (profiling() == enabled || !source_->set_section_profiling(enabled))
    return;
  snapshot_ = source_->snapshot();
  update_profiling_command();
  refresh_summary();
}

void FrameProfilerController::clear() {
  if (!source_ || !source_->clear_capture())
    return;
  snapshot_ = source_->snapshot();
  observed_revision_ = snapshot_->revision;
  const bool session_changed =
      snapshot_->identity.source_id != observed_source_id_ ||
      snapshot_->identity.session_id != observed_session_id_;
  if (session_changed) {
    observed_source_id_ = snapshot_->identity.source_id;
    observed_session_id_ = snapshot_->identity.session_id;
    selected_frame_number_ = -1;
    follow_latest_ = true;
    commands_->set_checked(follow_command_, true);
  }
  selected_frame_number_ = -1;
  timeline_->clear();
  sections_->clear();
  refresh_models();
}

void FrameProfilerController::close() {
  if (!source_)
    return;
  source_->close();
  if (local_source_)
    local_source_->close();
  snapshot_ = source_->snapshot();
  update_capability_commands();
  update_capture_command();
  update_profiling_command();
}

bool FrameProfilerController::connect_remote(
    std::uint16_t port, std::string authentication_token) {
  if (port == 0 || authentication_token.empty())
    return false;
  auto remote = std::make_unique<RemoteFrameProfilerSource>(capacity());
  profiler_remote::ClientConfig config;
  config.port = port;
  config.authentication_token = std::move(authentication_token);
  if (!remote->connect(std::move(config)))
    return false;
  if (!local_source_)
    local_source_ = std::move(source_);
  else
    source_->close();
  local_source_->pause_capture();
  source_ = std::move(remote);
  snapshot_ = source_->snapshot();
  observed_revision_ = 0;
  observed_source_id_.clear();
  observed_session_id_.clear();
  selected_frame_number_ = -1;
  follow_latest_ = true;
  commands_->set_checked(follow_command_, true);
  refresh_models();
  return true;
}

bool FrameProfilerController::disconnect_remote() {
  if (!local_source_)
    return false;
  source_->close();
  source_ = std::move(local_source_);
  snapshot_ = source_->snapshot();
  observed_revision_ = 0;
  observed_source_id_.clear();
  observed_session_id_.clear();
  selected_frame_number_ = -1;
  follow_latest_ = true;
  commands_->set_checked(follow_command_, true);
  refresh_models();
  return true;
}

bool FrameProfilerController::update() {
  if (!source_)
    return false;
  const auto revision = source_->revision();
  if (revision == observed_revision_)
    return false;
  const auto now = std::chrono::steady_clock::now();
  if (has_refreshed_ &&
      now - last_refresh_time_ < std::chrono::milliseconds(100)) {
    return false;
  }
  snapshot_ = source_->snapshot();
  observed_revision_ = snapshot_->revision;
  if (follow_latest_) {
    selected_frame_number_ =
        snapshot_->frames.empty() ? -1 : snapshot_->frames.back().frame_number;
  } else if (selected_frame_number_ >= 0 &&
             !snapshot_->find(selected_frame_number_)) {
    selected_frame_number_ = -1;
  }
  refresh_models();
  last_refresh_time_ = now;
  has_refreshed_ = true;
  return true;
}

bool FrameProfilerController::activate(gui_native::CommandId id) {
  if (!commands_->contains(id))
    return false;
  if (!commands_->command(id).data.enabled)
    return false;
  if (id == capture_command_) {
    capturing() ? pause() : start_capture();
  } else if (id == profiling_command_) {
    set_profiling(!profiling());
  } else if (id == clear_command_) {
    clear();
  } else if (id == follow_command_) {
    follow_latest_ = !follow_latest_;
    commands_->set_checked(follow_command_, follow_latest_);
    if (follow_latest_) {
      selected_frame_number_ = snapshot_->frames.empty()
                                   ? -1
                                   : snapshot_->frames.back().frame_number;
      refresh_selected_frame();
    }
  } else if (id == include_ui_command_) {
    if (source_->set_include_ui(!snapshot_->status.include_ui)) {
      snapshot_ = source_->snapshot();
      commands_->set_checked(include_ui_command_, snapshot_->status.include_ui);
    }
  } else if (id == previous_hitch_command_) {
    select_adjacent_hitch(-1);
  } else if (id == next_hitch_command_) {
    select_adjacent_hitch(1);
  } else {
    return false;
  }
  return true;
}

bool FrameProfilerController::select_frame(std::int64_t frame_number) {
  if (!snapshot_ || !snapshot_->find(frame_number))
    return false;
  selected_frame_number_ = frame_number;
  follow_latest_ = false;
  commands_->set_checked(follow_command_, false);
  refresh_selected_frame();
  return true;
}

bool FrameProfilerController::select_adjacent_hitch(int direction) {
  if (direction > 0) {
    for (const auto &frame : snapshot_->frames) {
      if (frame_is_hitch(frame, hitch_ratio_) &&
          frame.frame_number > selected_frame_number_) {
        return select_frame(frame.frame_number);
      }
    }
  } else {
    const auto selected =
        selected_frame_number_ >= 0 ? selected_frame_number_ : INT64_MAX;
    for (auto iterator = snapshot_->frames.rbegin();
         iterator != snapshot_->frames.rend(); ++iterator) {
      if (frame_is_hitch(*iterator, hitch_ratio_) &&
          iterator->frame_number < selected) {
        return select_frame(iterator->frame_number);
      }
    }
  }
  return false;
}

void FrameProfilerController::refresh_models() {
  update_capability_commands();
  update_capture_command();
  update_profiling_command();
  refresh_timeline();
  refresh_summary();
  refresh_selected_frame();
}

void FrameProfilerController::refresh_timeline() {
  if (!snapshot_ || snapshot_->frames.empty()) {
    timeline_->clear();
    return;
  }
  std::vector<gui_native::FrameTimelineSample> samples;
  samples.reserve(snapshot_->frames.size());
  for (const auto &frame : snapshot_->frames) {
    samples.push_back({
        frame.frame_number,
        static_cast<float>(frame.interval_ms),
        static_cast<float>(frame.active_ms),
        static_cast<float>(frame.deadline_lateness_ms),
        static_cast<float>(frame.target_interval_ms),
        frame_is_hitch(frame, hitch_ratio_),
        has_gap_before(*snapshot_, frame),
    });
  }
  timeline_->set_samples(std::move(samples));
}

void FrameProfilerController::refresh_summary() {
  const auto stats = statistics(*snapshot_, hitch_ratio_);
  const char *profiling_state =
      snapshot_->status.profiling_sections
          ? "on"
          : (snapshot_->status.external_profiling ? "external" : "off");
  std::ostringstream text;
  text << (snapshot_->status.capturing ? "Capturing" : "Paused")
       << " | profiling " << profiling_state << " | " << stats.frame_count
       << " frames | p50 " << milliseconds(stats.interval_p50_ms, 2)
       << " ms | p95 " << milliseconds(stats.interval_p95_ms, 2) << " ms | p99 "
       << milliseconds(stats.interval_p99_ms, 2) << " ms | max "
       << milliseconds(stats.max_interval_ms, 2) << " ms | hitches "
       << stats.hitch_count;
  summary_->set_text(text.str());
  status_->set_text(
      snapshot_->identity.display_name + " / " +
      snapshot_->identity.session_id +
      (snapshot_->status.connected ? " | connected" : " | disconnected") +
      " | History overwritten: " +
      std::to_string(snapshot_->status.overwritten_frames) +
      " | transport drops: " +
      std::to_string(snapshot_->status.dropped_frames) +
      " | " + snapshot_->status.detail +
      " | Mouse wheel: scroll history | Ctrl+wheel: zoom timeline | Arrow "
      "keys: select frame");
}

void FrameProfilerController::refresh_selected_frame() {
  const FrameProfilerFrame *frame =
      selected_frame_number_ >= 0 ? snapshot_->find(selected_frame_number_)
                                  : nullptr;
  if (!frame) {
    sections_->clear();
    detail_->set_html("<b>No frame selected</b>");
    return;
  }

  std::vector<gui_native::TreeTableRowData> rows;
  rows.reserve(frame->sections.size());
  const double denominator = frame->active_ms;
  for (std::size_t index = 0; index < frame->sections.size(); ++index) {
    const FrameProfilerSection &section = frame->sections[index];
    const double inclusive = std::max(section.cpu_ms, 0.0);
    const double children = std::max(section.children_ms, 0.0);
    const bool has_children = section.first_child >= 0;
    rows.push_back({
        section_id(static_cast<int>(index)),
        section.parent_index >= 0 ? section_id(section.parent_index) : "",
        {
            section.name,
            milliseconds(inclusive),
            milliseconds(std::max(inclusive - children, 0.0)),
            milliseconds(
                denominator > 0.0 ? inclusive / denominator * 100.0 : 0.0, 1) +
                "%",
            has_children
                ? milliseconds(
                      inclusive > 0.0 ? children / inclusive * 100.0 : 0.0, 0) +
                      "%"
                : "",
            section.call_count > 1 ? std::to_string(section.call_count) : "",
        },
    });
  }
  sections_->set_rows(std::move(rows));

  bool has_pacing_gap = false;
  double pacing_gap_ms = 0.0;
  const auto found =
      std::find_if(snapshot_->frames.begin(), snapshot_->frames.end(),
                   [frame](const auto &candidate) {
                     return candidate.frame_number == frame->frame_number;
                   });
  if (found != snapshot_->frames.begin() && found != snapshot_->frames.end() &&
      !has_gap_before(*snapshot_, *found) && found->interval_ms > 0.0) {
    pacing_gap_ms = std::max(found->interval_ms - (found - 1)->active_ms, 0.0);
    has_pacing_gap = true;
  }
  const std::string gap =
      has_pacing_gap ? milliseconds(pacing_gap_ms) + " ms" : "—";
  detail_->set_html(
      "<b>Frame " + std::to_string(frame->frame_number) + "</b><br>" +
      "Interval: " + milliseconds(frame->interval_ms) + " ms<br>" +
      "Active: " + milliseconds(frame->active_ms) + " ms<br>" +
      "Sections: " + (frame->sections_profiled ? "profiled" : "not profiled") +
      "<br>" + "Pacing gap: " + gap + "<br>" +
      "Target: " + milliseconds(frame->target_interval_ms) + " ms<br>" +
      "Deadline lateness: " + milliseconds(frame->deadline_lateness_ms) +
      " ms<br>" +
      "Missed intervals: " + std::to_string(frame->missed_intervals) + "<br>" +
      "Hitch: " + (frame_is_hitch(*frame, hitch_ratio_) ? "yes" : "no"));
}

void FrameProfilerController::show_section_details(
    gui_native::TreeTableNodeId node) {
  if (!sections_->contains(node))
    return;
  const auto &cells = sections_->node(node).data.cells;
  if (cells.size() < 6)
    return;
  detail_->set_html(
      "<b>" + cells[0] + "</b><br>Inclusive: " + cells[1] +
      " ms<br>Self: " + cells[2] + " ms<br>Frame share: " + cells[3] +
      "<br>Child coverage: " + (cells[4].empty() ? "—" : cells[4]) +
      "<br>Calls: " + (cells[5].empty() ? "1" : cells[5]));
}

void FrameProfilerController::update_capture_command() {
  auto data = commands_->command(capture_command_).data;
  const std::string label = capturing() ? "Pause" : "Capture";
  if (data.label == label && data.checked == capturing())
    return;
  data.label = label;
  data.checked = capturing();
  commands_->update(capture_command_, std::move(data));
}

void FrameProfilerController::update_profiling_command() {
  auto data = commands_->command(profiling_command_).data;
  if (data.checked == profiling())
    return;
  data.checked = profiling();
  commands_->update(profiling_command_, std::move(data));
}

void FrameProfilerController::update_capability_commands() {
  const auto capabilities = snapshot_ ? snapshot_->capabilities : 0;
  commands_->set_enabled(
      capture_command_,
      has_capability(capabilities, FrameProfilerCapability::Capture));
  commands_->set_enabled(
      profiling_command_,
      has_capability(capabilities, FrameProfilerCapability::SectionProfiling));
  commands_->set_enabled(
      clear_command_,
      has_capability(capabilities, FrameProfilerCapability::Clear));
  commands_->set_enabled(
      include_ui_command_,
      has_capability(capabilities, FrameProfilerCapability::IncludeUi));
  commands_->set_checked(include_ui_command_,
                         snapshot_ && snapshot_->status.include_ui);
}

} // namespace termin
