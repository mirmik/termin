#include "termin/frame_profiler/frame_profiler_source.hpp"

#include <algorithm>
#include <stdexcept>
#include <utility>

#include <tc_profiler.h>
#include <tcbase/tc_log.h>
#include <termin/engine/engine_core.hpp>

namespace termin {
    namespace {

        class LocalFrameProfilerSource final : public IFrameProfilerSource {
        public:
            LocalFrameProfilerSource(EngineCore& engine, int capacity)
                : engine_(&engine),
                  capacity_(capacity) {
                if (capacity <= 0) {
                    tc_log_error("local frame profiler: capture capacity must be positive");
                    throw std::invalid_argument("profiler capture capacity must be positive");
                }
                capture_ = tc_profiler_capture_create(capacity);
                if (!capture_) {
                    tc_log_error("local frame profiler: failed to create native capture");
                    throw std::runtime_error("failed to create native profiler capture");
                }
                rebuild_snapshot();
            }

            ~LocalFrameProfilerSource() override {
                close();
            }

            std::uint64_t revision() const override {
                return capture_ ? tc_profiler_capture_revision(capture_) : snapshot_->revision;
            }

            std::shared_ptr<const FrameProfilerSnapshot> snapshot() override {
                if (capture_ && snapshot_->revision != tc_profiler_capture_revision(capture_)) {
                    rebuild_snapshot();
                } else if (capture_) {
                    refresh_status();
                }
                return snapshot_;
            }

            bool start_capture() override {
                if (!capture_)
                    return false;
                tc_profiler_capture_set_active(capture_, true);
                refresh_status();
                return true;
            }

            bool pause_capture() override {
                if (!capture_)
                    return false;
                tc_profiler_capture_set_active(capture_, false);
                refresh_status();
                return true;
            }

            bool set_section_profiling(bool enabled) override {
                if (!capture_)
                    return false;
                tc_profiler_capture_set_profiling(capture_, enabled);
                refresh_status();
                return true;
            }

            bool clear_capture() override {
                if (!capture_)
                    return false;
                tc_profiler_capture_clear(capture_);
                rebuild_snapshot();
                return true;
            }

            bool set_include_ui(bool enabled) override {
                if (!engine_)
                    return false;
                engine_->set_profile_ui(enabled);
                refresh_status();
                return true;
            }

            void close() override {
                if (!capture_)
                    return;
                tc_profiler_capture_set_active(capture_, false);
                tc_profiler_capture_set_profiling(capture_, false);
                tc_profiler_capture_destroy(capture_);
                capture_ = nullptr;
                auto closed = std::make_shared<FrameProfilerSnapshot>(*snapshot_);
                closed->status.connected = false;
                closed->status.capturing = false;
                closed->status.profiling_sections = false;
                closed->status.detail = "local capture closed";
                closed->capabilities = 0;
                ++closed->revision;
                snapshot_ = std::move(closed);
            }

        private:
            void refresh_status() {
                auto current = std::make_shared<FrameProfilerSnapshot>(*snapshot_);
                current->status.connected = capture_ != nullptr;
                current->status.capturing = tc_profiler_capture_active(capture_);
                current->status.profiling_sections = tc_profiler_capture_profiling(capture_);
                current->status.external_profiling = tc_profiler_enabled() && !current->status.profiling_sections;
                current->status.include_ui = engine_ && engine_->profile_ui();
                current->status.detail = "in-process capture";
                snapshot_ = std::move(current);
            }

            void rebuild_snapshot() {
                auto next = std::make_shared<FrameProfilerSnapshot>();
                next->revision = tc_profiler_capture_revision(capture_);
                next->capacity = static_cast<std::size_t>(capacity_);
                next->identity = {"local", "process", "Local process"};
                next->capabilities = FrameProfilerCapability::Capture | FrameProfilerCapability::SectionProfiling |
                                     FrameProfilerCapability::Clear | FrameProfilerCapability::IncludeUi;

                const int count = tc_profiler_capture_count(capture_);
                next->frames.reserve(static_cast<std::size_t>(count));
                for (int index = 0; index < count; ++index) {
                    const tc_frame_profile* source = tc_profiler_capture_at(capture_, index);
                    if (!source) {
                        tc_log_error("local frame profiler: capture returned null frame at %d", index);
                        continue;
                    }
                    FrameProfilerFrame frame;
                    frame.frame_number = source->frame_number;
                    frame.start_time_ms = source->start_time_ms;
                    frame.interval_ms = source->interval_ms;
                    frame.active_ms = source->active_ms;
                    frame.gpu_duration_ms = source->gpu_duration_ms;
                    frame.has_gpu_duration = source->has_gpu_duration;
                    frame.target_interval_ms = source->target_interval_ms;
                    frame.deadline_lateness_ms = source->deadline_lateness_ms;
                    frame.missed_intervals =
                        source->missed_intervals > 0 ? static_cast<std::uint32_t>(source->missed_intervals) : 0;
                    frame.sections_profiled = source->sections_profiled;
                    frame.sections.reserve(static_cast<std::size_t>(source->section_count));
                    for (int section_index = 0; section_index < source->section_count; ++section_index) {
                        const tc_section_timing& section = source->sections[section_index];
                        frame.sections.push_back({
                            section.name,
                            section.cpu_ms,
                            section.children_ms,
                            section.call_count > 0 ? static_cast<std::uint32_t>(section.call_count) : 0,
                            section.parent_index,
                            section.first_child,
                            section.next_sibling,
                        });
                    }
                    if (!next->frames.empty() && frame.frame_number != next->frames.back().frame_number + 1) {
                        frame.gap_before = true;
                        next->gaps.push_back({
                            FrameProfilerGapKind::Source,
                            next->frames.back().frame_number + 1,
                            frame.frame_number - 1,
                            static_cast<std::uint64_t>(
                                std::max<std::int64_t>(0, frame.frame_number - next->frames.back().frame_number - 1)),
                            "non-contiguous source frames",
                        });
                    }
                    next->frames.push_back(std::move(frame));
                }

                const int overwritten = tc_profiler_capture_overwritten_count(capture_);
                if (overwritten > 0 && !next->frames.empty()) {
                    next->frames.front().gap_before = true;
                    next->gaps.insert(next->gaps.begin(),
                                      {
                                          FrameProfilerGapKind::CaptureOverwrite,
                                          next->frames.front().frame_number - overwritten,
                                          next->frames.front().frame_number - 1,
                                          static_cast<std::uint64_t>(overwritten),
                                          "bounded local history overwritten",
                                      });
                }
                next->status.overwritten_frames = overwritten > 0 ? static_cast<std::uint64_t>(overwritten) : 0;
                snapshot_ = std::move(next);
                refresh_status();
            }

            EngineCore* engine_ = nullptr;
            tc_profiler_capture* capture_ = nullptr;
            int capacity_ = 0;
            std::shared_ptr<FrameProfilerSnapshot> snapshot_;
        };

    } // namespace

    std::unique_ptr<IFrameProfilerSource> make_local_frame_profiler_source(EngineCore& engine, int capacity) {
        return std::make_unique<LocalFrameProfilerSource>(engine, capacity);
    }

} // namespace termin
