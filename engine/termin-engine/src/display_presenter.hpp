#pragma once

#include "termin/render/rendering_manager.hpp"

#include <array>

namespace termin::rendering_manager_detail {

    bool present_display(RenderingManager& manager, tc_display_handle display);

    class DisplayPresentationCache {
    private:
        struct ViewportState {
            uint64_t viewport;
            uint64_t target;
            uint64_t output_revision;
            std::array<int, 4> rect;
            int depth;
            bool operator==(const ViewportState&) const = default;
        };
        struct DisplayState {
            const tc_render_surface* surface = nullptr;
            uint32_t texture = 0;
            int width = 0;
            int height = 0;
            std::vector<ViewportState> viewports;
            bool operator==(const DisplayState&) const = default;
        };

        DisplayState current_;
        std::unordered_map<uint64_t, DisplayState> presentations_;

    public:
        void present_pending(RenderingManager& manager, const OffscreenRenderPlanner& planner, tc_display_handle display);
        void invalidate(tc_display_handle display);
        void clear();
    };

} // namespace termin::rendering_manager_detail
