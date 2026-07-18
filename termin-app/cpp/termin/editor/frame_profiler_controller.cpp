#include "termin/editor/frame_profiler_controller.hpp"

#include <algorithm>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include <tc_profiler.h>
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

std::string section_id(int index) {
    return "section-" + std::to_string(index);
}

std::string milliseconds(double value, int precision = 3) {
    std::ostringstream stream;
    stream << std::fixed << std::setprecision(precision) << value;
    return stream.str();
}

} // namespace

FrameProfilerController::FrameProfilerController(EngineCore& engine, int capacity,
                                                 double hitch_ratio)
    : engine_(&engine), capacity_(capacity), hitch_ratio_(hitch_ratio),
      commands_(std::make_shared<gui_native::CommandModel>()),
      timeline_(std::make_shared<gui_native::FrameTimelineModel>()),
      sections_(std::make_shared<gui_native::TreeTableModel>()),
      summary_(std::make_shared<gui_native::RichTextModel>()),
      detail_(std::make_shared<gui_native::RichTextModel>()),
      status_(std::make_shared<gui_native::RichTextModel>()) {
    if (capacity <= 0) throw std::invalid_argument("profiler capture capacity must be positive");
    if (hitch_ratio <= 1.0) throw std::invalid_argument("profiler hitch ratio must exceed one");
    capture_ = tc_profiler_capture_create(capacity);
    if (!capture_) throw std::runtime_error("failed to create native profiler capture");

    capture_command_ = commands_->append(command("capture", "Capture", true));
    profiling_command_ = commands_->append(command("profiling", "Profiling", true));
    clear_command_ = commands_->append(command("clear", "Clear"));
    commands_->append(separator("separator-1"));
    follow_command_ = commands_->append(command("follow", "Follow", true, true));
    include_ui_command_ = commands_->append(
        command("include-ui", "Include UI", true, engine.profile_ui()));
    commands_->append(separator("separator-2"));
    previous_hitch_command_ = commands_->append(command("previous-hitch", "Previous Hitch"));
    next_hitch_command_ = commands_->append(command("next-hitch", "Next Hitch"));
    refresh_models();
}

FrameProfilerController::~FrameProfilerController() { close(); }

std::shared_ptr<gui_native::CommandModel> FrameProfilerController::command_model() const { return commands_; }
std::shared_ptr<gui_native::FrameTimelineModel> FrameProfilerController::timeline_model() const { return timeline_; }
std::shared_ptr<gui_native::TreeTableModel> FrameProfilerController::section_model() const { return sections_; }
std::shared_ptr<gui_native::RichTextModel> FrameProfilerController::summary_model() const { return summary_; }
std::shared_ptr<gui_native::RichTextModel> FrameProfilerController::detail_model() const { return detail_; }
std::shared_ptr<gui_native::RichTextModel> FrameProfilerController::status_model() const { return status_; }

void FrameProfilerController::start_capture() {
    if (capturing_ || !capture_) return;
    capturing_ = true;
    tc_profiler_capture_set_active(capture_, true);
    update_capture_command();
    refresh_summary();
}

void FrameProfilerController::pause() {
    if (!capturing_ || !capture_) return;
    tc_profiler_capture_set_active(capture_, false);
    capturing_ = false;
    update_capture_command();
    refresh_summary();
}

void FrameProfilerController::set_profiling(bool enabled) {
    if (!capture_ || profiling_ == enabled) return;
    profiling_ = enabled;
    tc_profiler_capture_set_profiling(capture_, profiling_);
    update_profiling_command();
    refresh_summary();
}

void FrameProfilerController::clear() {
    if (!capture_) return;
    tc_profiler_capture_clear(capture_);
    observed_revision_ = tc_profiler_capture_revision(capture_);
    timeline_last_frame_number_ = -1;
    selected_frame_number_ = -1;
    timeline_->clear();
    sections_->clear();
    refresh_models();
}

void FrameProfilerController::close() {
    if (!capture_) return;
    pause();
    tc_profiler_capture_destroy(capture_);
    capture_ = nullptr;
}

bool FrameProfilerController::update() {
    if (!capture_) return false;
    const auto revision = tc_profiler_capture_revision(capture_);
    if (revision == observed_revision_) return false;
    const auto now = std::chrono::steady_clock::now();
    if (has_refreshed_ && now - last_refresh_time_ < std::chrono::milliseconds(100)) {
        return false;
    }
    observed_revision_ = revision;
    if (follow_latest_) {
        const int count = tc_profiler_capture_count(capture_);
        const tc_frame_profile* newest = tc_profiler_capture_at(capture_, count - 1);
        selected_frame_number_ = newest ? newest->frame_number : -1;
    } else if (selected_frame_number_ >= 0 &&
               !tc_profiler_capture_find(capture_, selected_frame_number_)) {
        selected_frame_number_ = -1;
    }
    refresh_models();
    last_refresh_time_ = now;
    has_refreshed_ = true;
    return true;
}

bool FrameProfilerController::activate(gui_native::CommandId id) {
    if (!commands_->contains(id)) return false;
    if (id == capture_command_) {
        capturing_ ? pause() : start_capture();
    } else if (id == profiling_command_) {
        set_profiling(!profiling_);
    } else if (id == clear_command_) {
        clear();
    } else if (id == follow_command_) {
        follow_latest_ = !follow_latest_;
        commands_->set_checked(follow_command_, follow_latest_);
        if (follow_latest_) {
            const int count = tc_profiler_capture_count(capture_);
            const tc_frame_profile* newest = tc_profiler_capture_at(capture_, count - 1);
            selected_frame_number_ = newest ? newest->frame_number : -1;
            refresh_selected_frame();
        }
    } else if (id == include_ui_command_) {
        engine_->set_profile_ui(!engine_->profile_ui());
        commands_->set_checked(include_ui_command_, engine_->profile_ui());
    } else if (id == previous_hitch_command_) {
        select_adjacent_hitch(-1);
    } else if (id == next_hitch_command_) {
        select_adjacent_hitch(1);
    } else {
        return false;
    }
    return true;
}

bool FrameProfilerController::select_frame(int frame_number) {
    if (!capture_ || !tc_profiler_capture_find(capture_, frame_number)) return false;
    selected_frame_number_ = frame_number;
    follow_latest_ = false;
    commands_->set_checked(follow_command_, false);
    refresh_selected_frame();
    return true;
}

bool FrameProfilerController::select_adjacent_hitch(int direction) {
    const int count = tc_profiler_capture_count(capture_);
    if (direction > 0) {
        for (int index = 0; index < count; ++index) {
            tc_profiler_frame_summary frame{};
            if (tc_profiler_capture_summary_at(capture_, index, hitch_ratio_, &frame) &&
                frame.hitch && frame.frame_number > selected_frame_number_) {
                return select_frame(frame.frame_number);
            }
        }
    } else {
        const int selected = selected_frame_number_ >= 0 ? selected_frame_number_ : INT32_MAX;
        for (int index = count - 1; index >= 0; --index) {
            tc_profiler_frame_summary frame{};
            if (tc_profiler_capture_summary_at(capture_, index, hitch_ratio_, &frame) &&
                frame.hitch && frame.frame_number < selected) {
                return select_frame(frame.frame_number);
            }
        }
    }
    return false;
}

void FrameProfilerController::refresh_models() {
    refresh_timeline();
    refresh_summary();
    refresh_selected_frame();
}

void FrameProfilerController::refresh_timeline() {
    const int count = tc_profiler_capture_count(capture_);
    if (count == 0) {
        timeline_->clear();
        timeline_last_frame_number_ = -1;
        return;
    }
    const tc_frame_profile* oldest = tc_profiler_capture_at(capture_, 0);
    if (!oldest) return;
    if (timeline_last_frame_number_ >= 0 &&
        timeline_last_frame_number_ < oldest->frame_number - 1) {
        timeline_->clear();
        timeline_last_frame_number_ = -1;
    }
    tc_profiler_history_range range{};
    if (!tc_profiler_capture_after(capture_, timeline_last_frame_number_, &range)) {
        throw std::runtime_error("failed to query profiler capture timeline");
    }
    std::vector<gui_native::FrameTimelineSample> samples;
    samples.reserve(static_cast<size_t>(range.count));
    for (int offset = 0; offset < range.count; ++offset) {
        tc_profiler_frame_summary frame{};
        if (!tc_profiler_capture_summary_at(
                capture_, range.first_index + offset, hitch_ratio_, &frame)) {
            throw std::runtime_error("profiler capture changed while updating timeline");
        }
        samples.push_back({
            frame.frame_number,
            static_cast<float>(frame.interval_ms),
            static_cast<float>(frame.active_ms),
            static_cast<float>(frame.deadline_lateness_ms),
            static_cast<float>(frame.target_interval_ms),
            frame.hitch,
            frame.gap_before || (offset == 0 && range.dropped_count > 0),
        });
    }
    if (!samples.empty()) timeline_->append_samples(std::move(samples), static_cast<size_t>(capacity_));
    timeline_last_frame_number_ = range.newest_frame_number;
}

void FrameProfilerController::refresh_summary() {
    tc_profiler_statistics stats{};
    if (!tc_profiler_capture_statistics(capture_, -1, -1, hitch_ratio_, &stats)) {
        throw std::runtime_error("failed to calculate profiler capture statistics");
    }
    const char* profiling_state = profiling_
        ? "on"
        : (tc_profiler_enabled() ? "external" : "off");
    std::ostringstream text;
    text << (capturing_ ? "Capturing" : "Paused")
         << " | profiling " << profiling_state
         << " | " << stats.frame_count
         << " frames | p50 " << milliseconds(stats.interval_p50_ms, 2)
         << " ms | p95 " << milliseconds(stats.interval_p95_ms, 2)
         << " ms | p99 " << milliseconds(stats.interval_p99_ms, 2)
         << " ms | max " << milliseconds(stats.max_interval_ms, 2)
         << " ms | hitches " << stats.hitch_count;
    summary_->set_text(text.str());
    status_->set_text(
        "History overwritten: " + std::to_string(stats.overwritten_count) +
        " | Mouse wheel: scroll history | Ctrl+wheel: zoom timeline | Arrow keys: select frame");
}

void FrameProfilerController::refresh_selected_frame() {
    const tc_frame_profile* frame = selected_frame_number_ >= 0
        ? tc_profiler_capture_find(capture_, selected_frame_number_) : nullptr;
    if (!frame) {
        sections_->clear();
        detail_->set_html("<b>No frame selected</b>");
        return;
    }

    std::vector<gui_native::TreeTableRowData> rows;
    rows.reserve(static_cast<size_t>(frame->section_count));
    const double denominator = std::max(frame->active_ms, frame->total_ms);
    for (int index = 0; index < frame->section_count; ++index) {
        const tc_section_timing& section = frame->sections[index];
        const double inclusive = std::max(section.cpu_ms, 0.0);
        const double children = std::max(section.children_ms, 0.0);
        const bool has_children = section.first_child >= 0;
        rows.push_back({
            section_id(index),
            section.parent_index >= 0 ? section_id(section.parent_index) : "",
            {
                section.name,
                milliseconds(inclusive),
                milliseconds(std::max(inclusive - children, 0.0)),
                milliseconds(denominator > 0.0 ? inclusive / denominator * 100.0 : 0.0, 1) + "%",
                has_children ? milliseconds(inclusive > 0.0 ? children / inclusive * 100.0 : 0.0, 0) + "%" : "",
                section.call_count > 1 ? std::to_string(section.call_count) : "",
            },
        });
    }
    sections_->set_rows(std::move(rows));

    tc_profiler_frame_summary summary{};
    const int count = tc_profiler_capture_count(capture_);
    for (int index = 0; index < count; ++index) {
        const tc_frame_profile* candidate = tc_profiler_capture_at(capture_, index);
        if (candidate && candidate->frame_number == frame->frame_number) {
            tc_profiler_capture_summary_at(capture_, index, hitch_ratio_, &summary);
            break;
        }
    }
    const std::string gap = summary.has_pacing_gap ? milliseconds(summary.pacing_gap_ms) + " ms" : "—";
    detail_->set_html(
        "<b>Frame " + std::to_string(frame->frame_number) + "</b><br>" +
        "Interval: " + milliseconds(frame->interval_ms) + " ms<br>" +
        "Active: " + milliseconds(frame->active_ms) + " ms<br>" +
        "Sections: " + (frame->sections_profiled ? "profiled" : "not profiled") + "<br>" +
        "Pacing gap: " + gap + "<br>" +
        "Target: " + milliseconds(frame->target_interval_ms) + " ms<br>" +
        "Deadline lateness: " + milliseconds(frame->deadline_lateness_ms) + " ms<br>" +
        "Missed intervals: " + std::to_string(frame->missed_intervals) + "<br>" +
        "Hitch: " + (summary.hitch ? "yes" : "no"));
}

void FrameProfilerController::show_section_details(gui_native::TreeTableNodeId node) {
    if (!sections_->contains(node)) return;
    const auto& cells = sections_->node(node).data.cells;
    if (cells.size() < 6) return;
    detail_->set_html(
        "<b>" + cells[0] + "</b><br>Inclusive: " + cells[1] +
        " ms<br>Self: " + cells[2] + " ms<br>Frame share: " + cells[3] +
        "<br>Child coverage: " + (cells[4].empty() ? "—" : cells[4]) +
        "<br>Calls: " + (cells[5].empty() ? "1" : cells[5]));
}

void FrameProfilerController::update_capture_command() {
    auto data = commands_->command(capture_command_).data;
    data.label = capturing_ ? "Pause" : "Capture";
    data.checked = capturing_;
    commands_->update(capture_command_, std::move(data));
}

void FrameProfilerController::update_profiling_command() {
    auto data = commands_->command(profiling_command_).data;
    data.checked = profiling_;
    commands_->update(profiling_command_, std::move(data));
}

} // namespace termin
