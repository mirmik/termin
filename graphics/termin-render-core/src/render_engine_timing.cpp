#include "render_engine_timing.hpp"

#include <algorithm>
#include <cstdlib>
#include <utility>
#include <vector>

#include <tcbase/tc_log.hpp>

namespace termin {

    bool render_engine_timing_enabled() {
#ifdef __ANDROID__
        return true;
#else
        const char* env = std::getenv("TERMIN_RENDER_ENGINE_TIMING");
        return env && env[0] && env[0] != '0';
#endif
    }

    RenderEngineTimingStats& render_engine_timing_stats() {
        static RenderEngineTimingStats stats;
        return stats;
    }

    void maybe_report_render_engine_timing() {
        if (!render_engine_timing_enabled()) {
            return;
        }

        RenderEngineTimingStats& stats = render_engine_timing_stats();
        const auto now = RenderTimingClock::now();
        const double window_seconds = std::chrono::duration<double>(now - stats.window_start).count();
        if (window_seconds < 2.0 || stats.calls == 0) {
            return;
        }

        const double inv_calls = 1.0 / static_cast<double>(stats.calls);
        tc::Log::info("[RenderEngine timing] calls=%llu callsPerSec=%.1f avgMs{total=%.2f frameGraph=%.2f specs=%.2f "
                      "allocate=%.2f beginFrame=%.2f clearTargets=%.2f assemble=%.2f clearResources=%.2f passes=%.2f "
                      "endFrame=%.2f} avgRenderItems{sceneTraversals=%.2f producers=%.2f items=%.2f}",
                      static_cast<unsigned long long>(stats.calls),
                      static_cast<double>(stats.calls) / window_seconds,
                      stats.total_ms * inv_calls,
                      stats.frame_graph_ms * inv_calls,
                      stats.specs_ms * inv_calls,
                      stats.allocate_ms * inv_calls,
                      stats.begin_frame_ms * inv_calls,
                      stats.clear_targets_ms * inv_calls,
                      stats.assemble_resources_ms * inv_calls,
                      stats.clear_resources_ms * inv_calls,
                      stats.pass_total_ms * inv_calls,
                      stats.end_frame_ms * inv_calls,
                      static_cast<double>(stats.render_item_scene_traversals) * inv_calls,
                      static_cast<double>(stats.render_item_producers) * inv_calls,
                      static_cast<double>(stats.render_items) * inv_calls);

        std::vector<std::pair<std::string, RenderPassTimingStats>> passes;
        passes.reserve(stats.pass_stats.size());
        for (const auto& entry : stats.pass_stats) {
            passes.push_back(entry);
        }
        std::sort(passes.begin(), passes.end(), [](const auto& a, const auto& b) {
            return a.second.total_ms > b.second.total_ms;
        });

        const size_t max_passes = std::min<size_t>(passes.size(), 10);
        for (size_t i = 0; i < max_passes; ++i) {
            const auto& [name, pass] = passes[i];
            const double avg_ms = pass.count > 0 ? pass.total_ms / static_cast<double>(pass.count) : 0.0;
            tc::Log::info("[RenderEngine timing] pass[%zu] name='%s' calls=%llu avgMs=%.2f totalMs=%.2f",
                          i,
                          name.c_str(),
                          static_cast<unsigned long long>(pass.count),
                          avg_ms,
                          pass.total_ms);
        }

        stats = RenderEngineTimingStats{};
        stats.window_start = now;
    }

} // namespace termin
