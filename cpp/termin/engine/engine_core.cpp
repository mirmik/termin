// engine_core.cpp - EngineCore implementation
#include "engine_core.hpp"

#include <chrono>
#include <thread>

extern "C" {
#include "tc_log.h"
}

namespace termin {

EngineCore::EngineCore() {
    tc_engine_core_set_instance(reinterpret_cast<tc_engine_core*>(this));
    tc_log(TC_LOG_INFO, "[EngineCore] Created");
}

EngineCore::~EngineCore() {
    if (tc_engine_core_instance() == reinterpret_cast<tc_engine_core*>(this)) {
        tc_engine_core_set_instance(nullptr);
    }
    tc_log(TC_LOG_INFO, "[EngineCore] Destroyed");
}

void EngineCore::run() {
    _running = true;

    const double target_frame_time = 1.0 / _target_fps;
    auto last_time = std::chrono::high_resolution_clock::now();

    tc_log(TC_LOG_INFO, "[EngineCore] Starting main loop at %.1f FPS", _target_fps);

    while (_running) {
        auto frame_start = std::chrono::high_resolution_clock::now();
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
        scene_manager.tick_and_render(dt);

        // Frame limiting
        auto elapsed = std::chrono::high_resolution_clock::now() - frame_start;
        double elapsed_sec = std::chrono::duration<double>(elapsed).count();
        if (elapsed_sec < target_frame_time) {
            std::this_thread::sleep_for(
                std::chrono::duration<double>(target_frame_time - elapsed_sec)
            );
        }
    }

    tc_log(TC_LOG_INFO, "[EngineCore] Main loop stopped");

    // Shutdown callback (cleanup)
    if (_on_shutdown_callback) {
        _on_shutdown_callback();
    }
}

} // namespace termin
