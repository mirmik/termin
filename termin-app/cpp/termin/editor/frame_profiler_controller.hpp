#pragma once

#include <chrono>
#include <cstdint>
#include <memory>
#include <string>

#include "termin/editor/frame_profiler_source.hpp"

#include <termin/gui_native/command_model.hpp>
#include <termin/gui_native/frame_timeline.hpp>
#include <termin/gui_native/rich_text_model.hpp>
#include <termin/gui_native/tree_table_model.hpp>

namespace termin {

    class EngineCore;

    class FrameProfilerController {
    public:
        FrameProfilerController(EngineCore& engine, int capacity = 3600, double hitch_ratio = 1.25);
        FrameProfilerController(std::unique_ptr<IFrameProfilerSource> source, double hitch_ratio = 1.25);
        ~FrameProfilerController();

        FrameProfilerController(const FrameProfilerController&) = delete;
        FrameProfilerController& operator=(const FrameProfilerController&) = delete;

        std::shared_ptr<gui_native::CommandModel> command_model() const;
        std::shared_ptr<gui_native::FrameTimelineModel> timeline_model() const;
        std::shared_ptr<gui_native::TreeTableModel> section_model() const;
        std::shared_ptr<gui_native::RichTextModel> summary_model() const;
        std::shared_ptr<gui_native::RichTextModel> detail_model() const;
        std::shared_ptr<gui_native::RichTextModel> status_model() const;

        int capacity() const;
        double hitch_ratio() const {
            return hitch_ratio_;
        }
        bool capturing() const;
        bool profiling() const;
        bool follow_latest() const {
            return follow_latest_;
        }
        std::int64_t selected_frame_number() const {
            return selected_frame_number_;
        }

        void start_capture();
        void pause();
        void set_profiling(bool enabled);
        void clear();
        void close();
        bool update();
        bool activate(gui_native::CommandId command);
        bool select_frame(std::int64_t frame_number);
        void show_section_details(gui_native::TreeTableNodeId node);
        bool connect_remote(std::uint16_t port, std::string authentication_token);
        bool disconnect_remote();
        bool using_remote_source() const {
            return local_source_ != nullptr;
        }

    private:
        void refresh_models();
        void refresh_timeline();
        void refresh_summary();
        void refresh_selected_frame();
        void update_capture_command();
        void update_profiling_command();
        void update_capability_commands();
        bool select_adjacent_hitch(int direction);

        std::unique_ptr<IFrameProfilerSource> source_;
        std::unique_ptr<IFrameProfilerSource> local_source_;
        std::shared_ptr<const FrameProfilerSnapshot> snapshot_;
        double hitch_ratio_ = 0.0;
        bool follow_latest_ = true;
        std::int64_t selected_frame_number_ = -1;
        std::uint64_t observed_revision_ = 0;
        std::string observed_source_id_;
        std::string observed_session_id_;
        std::chrono::steady_clock::time_point last_refresh_time_{};
        bool has_refreshed_ = false;

        std::shared_ptr<gui_native::CommandModel> commands_;
        std::shared_ptr<gui_native::FrameTimelineModel> timeline_;
        std::shared_ptr<gui_native::TreeTableModel> sections_;
        std::shared_ptr<gui_native::RichTextModel> summary_;
        std::shared_ptr<gui_native::RichTextModel> detail_;
        std::shared_ptr<gui_native::RichTextModel> status_;

        gui_native::CommandId capture_command_ = gui_native::kInvalidCommandId;
        gui_native::CommandId profiling_command_ = gui_native::kInvalidCommandId;
        gui_native::CommandId clear_command_ = gui_native::kInvalidCommandId;
        gui_native::CommandId follow_command_ = gui_native::kInvalidCommandId;
        gui_native::CommandId include_ui_command_ = gui_native::kInvalidCommandId;
        gui_native::CommandId previous_hitch_command_ = gui_native::kInvalidCommandId;
        gui_native::CommandId next_hitch_command_ = gui_native::kInvalidCommandId;
    };

} // namespace termin
