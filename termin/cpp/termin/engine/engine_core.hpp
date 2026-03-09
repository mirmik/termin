// engine_core.hpp - Core engine runtime
//
// EngineCore owns SceneManager and RenderingManager.
// Editor connects to EngineCore rather than owning managers directly.
#pragma once

#include "termin/scene/scene_manager.hpp"
#include "termin/render/rendering_manager.hpp"

extern "C" {
#include "engine/tc_engine_core.h"
}

#include <functional>
#include <atomic>

namespace termin {

// EngineCore - owns SceneManager and RenderingManager
class EngineCore {
public:
    SceneManager scene_manager;
    RenderingManager rendering_manager;

private:
    std::atomic<bool> _running{false};
    double _target_fps = 60.0;

    // Callbacks for external integration (set from Python)
    std::function<void()> _poll_events_callback;
    std::function<bool()> _should_continue_callback;
    std::function<void()> _on_shutdown_callback;

public:
    EngineCore();
    ~EngineCore();

    // Singleton access (via C API for cross-DLL safety)
    static EngineCore* instance() {
        return reinterpret_cast<EngineCore*>(tc_engine_core_instance());
    }

    // Disable copy
    EngineCore(const EngineCore&) = delete;
    EngineCore& operator=(const EngineCore&) = delete;

    // --- Configuration ---
    void set_target_fps(double fps) { _target_fps = fps; }
    double target_fps() const { return _target_fps; }

    // --- Callbacks ---
    // Called each frame to process UI/input events (Qt, SDL)
    void set_poll_events_callback(std::function<void()> cb) { _poll_events_callback = std::move(cb); }

    // Called each frame to check if loop should continue
    void set_should_continue_callback(std::function<bool()> cb) { _should_continue_callback = std::move(cb); }

    // Called after main loop ends (for cleanup)
    void set_on_shutdown_callback(std::function<void()> cb) { _on_shutdown_callback = std::move(cb); }

    // --- Main loop ---
    // Run blocking main loop. Calls poll_events, tick_and_render at target_fps.
    // Returns when should_continue returns false or stop() is called.
    void run();

    // Stop the run() loop
    void stop() { _running = false; }

    // Check if running
    bool is_running() const { return _running; }
};

} // namespace termin
