#pragma once

#include <chrono>
#include <cstdint>
#include <string>
#include <unordered_map>

namespace termin {

    using RenderTimingClock = std::chrono::steady_clock;

    struct RenderPassTimingStats {
        uint64_t count = 0;
        double total_ms = 0.0;
    };

    struct RenderEngineTimingStats {
        RenderTimingClock::time_point window_start = RenderTimingClock::now();
        uint64_t calls = 0;
        double total_ms = 0.0;
        double frame_graph_ms = 0.0;
        double specs_ms = 0.0;
        double allocate_ms = 0.0;
        double begin_frame_ms = 0.0;
        double clear_targets_ms = 0.0;
        double assemble_resources_ms = 0.0;
        double clear_resources_ms = 0.0;
        double pass_total_ms = 0.0;
        double end_frame_ms = 0.0;
        uint64_t render_item_scene_traversals = 0;
        uint64_t render_item_producers = 0;
        uint64_t render_items = 0;
        std::unordered_map<std::string, RenderPassTimingStats> pass_stats;
    };

    bool render_engine_timing_enabled();
    RenderEngineTimingStats& render_engine_timing_stats();
    void maybe_report_render_engine_timing();

} // namespace termin
