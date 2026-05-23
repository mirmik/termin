// engine_core.cpp - EngineCore implementation
#include "termin/engine/engine_core.hpp"

#include <chrono>
#include <thread>

extern "C" {
#include <tcbase/tc_log.h>
#include "tc_profiler.h"
#include <termin_scene/termin_scene.h>
}

namespace termin {

EngineCore::EngineCore() {
    termin_scene_runtime_init();
    tc_engine_core_set_instance(reinterpret_cast<tc_engine_core*>(this));
    tc_log(TC_LOG_INFO, "[EngineCore] Created");
}

EngineCore::~EngineCore() {
    if (tc_engine_core_instance() == reinterpret_cast<tc_engine_core*>(this)) {
        tc_engine_core_set_instance(nullptr);
    }
    termin_scene_runtime_shutdown();
    tc_log(TC_LOG_INFO, "[EngineCore] Destroyed");
}

void EngineCore::set_poll_events_callback(std::function<void()> cb) {
    const bool has_cb = static_cast<bool>(cb);
    _poll_events_callback = std::move(cb);
    tc_log(TC_LOG_INFO,
           "[EngineCore] set_poll_events_callback this=%p has_callback=%d",
           (void*)this, has_cb ? 1 : 0);
}

void EngineCore::set_should_continue_callback(std::function<bool()> cb) {
    const bool has_cb = static_cast<bool>(cb);
    _should_continue_callback = std::move(cb);
    tc_log(TC_LOG_INFO,
           "[EngineCore] set_should_continue_callback this=%p has_callback=%d",
           (void*)this, has_cb ? 1 : 0);
}

void EngineCore::set_on_shutdown_callback(std::function<void()> cb) {
    const bool has_cb = static_cast<bool>(cb);
    _on_shutdown_callback = std::move(cb);
    tc_log(TC_LOG_INFO,
           "[EngineCore] set_on_shutdown_callback this=%p has_callback=%d",
           (void*)this, has_cb ? 1 : 0);
}

bool EngineCore::tick_and_render(double dt) {
    static uint64_t s_tick_calls = 0;
    ++s_tick_calls;
    const bool trace_probe = s_tick_calls <= 5 || (s_tick_calls % 600) == 0;
    if (trace_probe) {
        tc_log(TC_LOG_INFO, "[EngineCore] tick_and_render#%llu this=%p begin dt=%.6f",
               (unsigned long long)s_tick_calls, (void*)this, dt);
    }
    // Frame scope is owned by run() — tick_and_render only opens sections
    // inside the already-open frame. When called standalone (outside run),
    // sections are no-ops because current_frame is NULL.
    bool profile = tc_profiler_enabled();

    bool should_render = scene_manager.tick(dt);
    const bool trace = trace_probe || should_render;
    if (trace) {
        tc_log(TC_LOG_INFO,
               "[EngineCore] tick_and_render#%llu after tick should_render=%d",
               (unsigned long long)s_tick_calls, should_render ? 1 : 0);
    }

    if (should_render) {
        if (profile) tc_profiler_begin_section("SceneManager Before Render");
        scene_manager.before_render();
        if (profile) tc_profiler_end_section();

        if (profile) tc_profiler_begin_section("SceneManager Render");
        if (trace) {
            tc_log(TC_LOG_INFO, "[EngineCore] tick_and_render#%llu render_all begin",
                   (unsigned long long)s_tick_calls);
        }
        rendering_manager.render_all(true);
        if (trace) {
            tc_log(TC_LOG_INFO, "[EngineCore] tick_and_render#%llu render_all end",
                   (unsigned long long)s_tick_calls);
        }
        if (profile) tc_profiler_end_section();

        if (profile) tc_profiler_begin_section("SceneManager After Render");
        scene_manager.invoke_after_render();
        if (profile) tc_profiler_end_section();
    }

    if (trace) {
        tc_log(TC_LOG_INFO, "[EngineCore] tick_and_render#%llu end",
               (unsigned long long)s_tick_calls);
    }
    return should_render;
}

void EngineCore::run() {
    _running = true;

    using clock = std::chrono::high_resolution_clock;
    using duration = clock::duration;

    const auto frame_duration = std::chrono::duration_cast<duration>(
        std::chrono::duration<double>(1.0 / _target_fps)
    );
    auto next_frame_time = clock::now();
    auto last_time = next_frame_time;

    tc_log(TC_LOG_INFO,
           "[EngineCore] Starting main loop this=%p poll_cb=%d continue_cb=%d shutdown_cb=%d at %.1f FPS",
           (void*)this,
           _poll_events_callback ? 1 : 0,
           _should_continue_callback ? 1 : 0,
           _on_shutdown_callback ? 1 : 0,
           _target_fps);

    while (_running) {
        auto frame_start = clock::now();
        double dt = std::chrono::duration<double>(frame_start - last_time).count();
        last_time = frame_start;

        bool profile = tc_profiler_enabled();
        if (profile) tc_profiler_begin_frame();

        // Always wrap the UI callback in a section so the sub-sections
        // the callback opens (Events, Render Compose, …) are nested
        // under a single root instead of bubbling up as siblings of
        // SceneManager Render. When profile_ui is off the wrap is
        // *muted* — the section and everything inside it doesn't
        // record; callees don't need to know about the flag.
        if (profile) {
            if (_profile_ui) tc_profiler_begin_section("UI");
            else             tc_profiler_begin_section_muted("UI");
        }
        static uint64_t s_loop_frames = 0;
        ++s_loop_frames;
        const bool trace_loop = s_loop_frames <= 5 || (s_loop_frames % 600) == 0;
        if (trace_loop) {
            tc_log(TC_LOG_INFO,
                   "[EngineCore] loop#%llu this=%p poll_cb=%d before poll",
                   (unsigned long long)s_loop_frames,
                   (void*)this,
                   _poll_events_callback ? 1 : 0);
        }
        if (_poll_events_callback) _poll_events_callback();
        if (trace_loop) {
            tc_log(TC_LOG_INFO,
                   "[EngineCore] loop#%llu this=%p after poll",
                   (unsigned long long)s_loop_frames,
                   (void*)this);
        }
        if (profile) tc_profiler_end_section();

        // Check if should continue
        if (_should_continue_callback && !_should_continue_callback()) {
            if (profile) tc_profiler_end_frame();
            _running = false;
            break;
        }

        // Tick and render — opens its own sections inside the frame
        // scope owned by this function.
        tick_and_render(dt);

        if (profile) tc_profiler_end_frame();

        // Frame limiting with sleep_until for stable pacing
        next_frame_time += frame_duration;

        // If we're behind, skip ahead (don't try to catch up)
        auto now = clock::now();
        if (next_frame_time < now) {
            next_frame_time = now;
        }

        std::this_thread::sleep_until(next_frame_time);
    }

    tc_log(TC_LOG_INFO, "[EngineCore] Main loop stopped");

    // Shutdown callback (cleanup)
    if (_on_shutdown_callback) {
        _on_shutdown_callback();
    }
}

} // namespace termin
