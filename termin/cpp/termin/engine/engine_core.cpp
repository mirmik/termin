// engine_core.cpp - EngineCore implementation
#include "engine_core.hpp"

#include <chrono>
#include <thread>

extern "C" {
#include <tcbase/tc_log.h>
#include "tc_profiler.h"
#include "core/tc_scene_render_mount.h"
#include "core/tc_scene_render_state.h"
#include <termin_scene/termin_scene.h>
#include <termin_collision/termin_collision.h>
#include "physics/tc_collision_world.h"
}

namespace termin {

static void ensure_builtin_scene_extensions_registered() {
    tc_scene_render_mount_extension_init();
    tc_scene_render_state_extension_init();
    tc_collision_world_extension_init();
}

EngineCore::EngineCore() {
    termin_scene_runtime_init();
    termin_collision_runtime_init();
    ensure_builtin_scene_extensions_registered();
    tc_engine_core_set_instance(reinterpret_cast<tc_engine_core*>(this));
    tc_log(TC_LOG_INFO, "[EngineCore] Created");
}

EngineCore::~EngineCore() {
    if (tc_engine_core_instance() == reinterpret_cast<tc_engine_core*>(this)) {
        tc_engine_core_set_instance(nullptr);
    }
    termin_collision_runtime_shutdown();
    termin_scene_runtime_shutdown();
    tc_log(TC_LOG_INFO, "[EngineCore] Destroyed");
}

bool EngineCore::tick_and_render(double dt) {
    bool profile = tc_profiler_enabled();

    if (profile) tc_profiler_begin_frame();

    bool should_render = scene_manager.tick(dt);

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

    if (profile) tc_profiler_end_frame();

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

    tc_log(TC_LOG_INFO, "[EngineCore] Starting main loop at %.1f FPS", _target_fps);

    while (_running) {
        auto frame_start = clock::now();
        double dt = std::chrono::duration<double>(frame_start - last_time).count();
        last_time = frame_start;

        // Poll events (Qt, SDL, etc.)
        if (_poll_events_callback) {
            _poll_events_callback();
        }

        // Check if should continue
        if (_should_continue_callback && !_should_continue_callback()) {
            _running = false;
            break;
        }

        // Tick and render
        tick_and_render(dt);

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
