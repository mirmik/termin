// engine_core.cpp - EngineCore implementation
#include "termin/engine/engine_core.hpp"
#include "frame_cadence.hpp"

#include <chrono>
#include <thread>

extern "C" {
#include <tcbase/tc_log.h>
#include "tc_profiler.h"
#include <termin_scene/termin_scene.h>
}

namespace termin {

EngineCore::EngineCore()
    : rendering_manager(render_topology) {
    termin_scene_runtime_init();
    scene_manager.set_before_scene_destroy_guard([this](tc_scene_handle scene) {
        if (!render_topology.is_attached(scene)
                && render_topology.render_targets(scene).empty()
                && render_topology.viewports(scene).empty()) {
            return;
        }
        tc_log(
            TC_LOG_ERROR,
            "[EngineCore] Scene destruction requested with live render attachments; forcing detach"
        );
        rendering_manager.detach_scene_full(scene, true);
        if (render_topology.is_attached(scene)
                || !render_topology.render_targets(scene).empty()
                || !render_topology.viewports(scene).empty()) {
            tc_log(
                TC_LOG_ERROR,
                "[EngineCore] Mandatory render detach left live scene topology"
            );
        }
    });
    tc_log(TC_LOG_INFO, "[EngineCore] Created");
}

EngineCore::~EngineCore() {
    // Scene-owned render objects must be detached while scene handles and the
    // scene runtime are still alive. Member destructors run after this body.
    const std::vector<tc_scene_handle> attached_scenes(
        render_topology.attached_scenes().begin(),
        render_topology.attached_scenes().end()
    );
    for (tc_scene_handle scene : attached_scenes) {
        rendering_manager.detach_scene_full(scene, true);
    }
    scene_manager.close_all_scenes();
    rendering_manager.shutdown();
    termin_scene_runtime_shutdown();
    tc_log(TC_LOG_INFO, "[EngineCore] Destroyed");
}

void EngineCore::set_poll_events_callback(std::function<void()> cb) {
    _poll_events_callback = std::move(cb);
}

void EngineCore::set_should_continue_callback(std::function<bool()> cb) {
    _should_continue_callback = std::move(cb);
}

void EngineCore::set_on_shutdown_callback(std::function<void()> cb) {
    _on_shutdown_callback = std::move(cb);
}

bool EngineCore::tick_and_render(double dt) {
    // Frame scope is owned by run() — tick_and_render only opens sections
    // inside the already-open frame. When called standalone (outside run),
    // sections are no-ops because current_frame is NULL.
    bool profile = tc_profiler_enabled();

    if (profile) tc_profiler_begin_section("SceneManager Tick");
    bool should_render = scene_manager.tick(dt);
    if (profile) tc_profiler_end_section();

    if (should_render) {
        if (profile) tc_profiler_begin_section("SceneManager Before Render");
        scene_manager.before_render();
        if (profile) tc_profiler_end_section();

        if (profile) tc_profiler_begin_section("SceneManager Render");
        rendering_manager.render_all(true);
        if (profile) tc_profiler_end_section();

        if (profile) tc_profiler_begin_section("SceneManager After Render");
        scene_manager.invoke_after_render();
        if (profile) tc_profiler_end_section();
    }

    return should_render;
}

void EngineCore::run() {
    _running = true;

    using clock = std::chrono::steady_clock;
    using duration = clock::duration;

    const auto frame_duration = std::chrono::duration_cast<duration>(
        std::chrono::duration<double>(1.0 / _target_fps)
    );
    auto scheduled_frame_time = clock::now();
    auto last_time = scheduled_frame_time;
    bool has_previous_frame = false;
    const double target_interval_ms = 1000.0 / _target_fps;

    tc_log(TC_LOG_INFO, "[EngineCore] Starting main loop at %.1f FPS", _target_fps);

    while (_running) {
        auto frame_start = clock::now();
        double dt = std::chrono::duration<double>(frame_start - last_time).count();
        const double start_time_ms = std::chrono::duration<double, std::milli>(
            frame_start.time_since_epoch()
        ).count();
        const double previous_start_time_ms = std::chrono::duration<double, std::milli>(
            last_time.time_since_epoch()
        ).count();
        const double scheduled_start_time_ms = std::chrono::duration<double, std::milli>(
            scheduled_frame_time.time_since_epoch()
        ).count();
        const engine_detail::FrameCadenceObservation cadence =
            engine_detail::observe_frame_start(
                start_time_ms,
                previous_start_time_ms,
                scheduled_start_time_ms,
                target_interval_ms,
                has_previous_frame
            );
        if (!has_previous_frame || frame_start > scheduled_frame_time) {
            scheduled_frame_time = frame_start;
        }
        last_time = frame_start;
        has_previous_frame = true;

        const bool capture_frame = tc_profiler_frame_capture_enabled();
        if (capture_frame) {
            const tc_profiler_frame_info frame_info{
                cadence.start_time_ms,
                cadence.interval_ms,
                cadence.target_interval_ms,
                cadence.deadline_lateness_ms,
                cadence.missed_intervals,
            };
            tc_profiler_begin_frame_with_info(&frame_info);
        }
        const bool profile = tc_profiler_enabled();

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
        if (_poll_events_callback) _poll_events_callback();
        if (profile) tc_profiler_end_section();

        // Check if should continue
        if (_should_continue_callback && !_should_continue_callback()) {
            if (capture_frame) tc_profiler_end_frame();
            _running = false;
            break;
        }

        // Tick and render — opens its own sections inside the frame
        // scope owned by this function.
        tick_and_render(dt);

        if (capture_frame) tc_profiler_end_frame();

        // Frame limiting with sleep_until for stable pacing
        // Keep the expected start until the next iteration observes it. A
        // late frame is resynchronized above only after its lateness has been
        // recorded, so scheduler catch-up cannot erase hitch evidence.
        scheduled_frame_time += frame_duration;
        std::this_thread::sleep_until(scheduled_frame_time);
    }

    tc_log(TC_LOG_INFO, "[EngineCore] Main loop stopped");

    // Shutdown callback (cleanup)
    if (_on_shutdown_callback) {
        _on_shutdown_callback();
    }
}

} // namespace termin
