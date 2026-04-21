// engine_core.cpp - EngineCore implementation
#include "termin/engine/engine_core.hpp"

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
    // Frame scope is owned by run() — tick_and_render only opens sections
    // inside the already-open frame. When called standalone (outside run),
    // sections are no-ops because current_frame is NULL.
    bool profile = tc_profiler_enabled();

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

        bool profile = tc_profiler_enabled();
        if (profile) tc_profiler_begin_frame();

        // Poll events (Qt, SDL, etc.). When profile_ui is on, UI time
        // goes into a dedicated "UI" section; when off, the frame scope
        // still covers UI work but the panel sees no root for it, which
        // mirrors how hosts without profile_ui (e.g. Qt editor) look.
        bool profile_ui = profile && _profile_ui;
        if (profile_ui) tc_profiler_begin_section("UI");
        if (_poll_events_callback) _poll_events_callback();
        if (profile_ui) tc_profiler_end_section();

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
