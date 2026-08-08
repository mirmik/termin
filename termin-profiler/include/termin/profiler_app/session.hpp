#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>
#include <string_view>

#include <termin/frame_profiler/frame_profiler_controller.hpp>
#include <termin/frame_profiler/remote_frame_profiler_source.hpp>
#include <termin/gui_native/rich_text_model.hpp>

namespace termin::profiler_app {

    class RemoteProfilerSession {
    public:
        explicit RemoteProfilerSession(std::size_t capacity = 3600, double hitch_ratio = 1.25);
        ~RemoteProfilerSession();

        RemoteProfilerSession(const RemoteProfilerSession&) = delete;
        RemoteProfilerSession& operator=(const RemoteProfilerSession&) = delete;

        bool connect(std::string_view port_text, std::string authentication_token);
        void disconnect();
        void close();
        bool update();

        FrameProfilerController& profiler() {
            return *profiler_;
        }
        const FrameProfilerController& profiler() const {
            return *profiler_;
        }
        std::shared_ptr<gui_native::RichTextModel> connection_model() const {
            return connection_model_;
        }
        std::shared_ptr<gui_native::RichTextModel> gpu_summary_model() const {
            return gpu_summary_model_;
        }
        std::shared_ptr<gui_native::RichTextModel> gpu_detail_model() const {
            return gpu_detail_model_;
        }
        std::shared_ptr<const FrameProfilerSnapshot> snapshot() const;
        void refresh_gpu_presentation();
        bool connection_requested() const {
            return connection_requested_;
        }
        bool connected() const;
        std::uint16_t port() const {
            return port_;
        }

    private:
        void refresh_connection_model();
        void publish_validation_error(std::string detail);

        RemoteFrameProfilerSource* remote_source_ = nullptr;
        std::unique_ptr<FrameProfilerController> profiler_;
        std::shared_ptr<gui_native::RichTextModel> connection_model_;
        std::shared_ptr<gui_native::RichTextModel> gpu_summary_model_;
        std::shared_ptr<gui_native::RichTextModel> gpu_detail_model_;
        std::uint64_t observed_source_revision_ = 0;
        std::uint16_t port_ = 0;
        bool connection_requested_ = false;
        bool closed_ = false;
    };

} // namespace termin::profiler_app
