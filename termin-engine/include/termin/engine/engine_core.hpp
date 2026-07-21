// engine_core.hpp - Core engine runtime
//
// EngineCore owns SceneManager and RenderingManager.
// Editor connects to EngineCore rather than owning managers directly.
#pragma once

#include "termin/engine/termin_engine_api.hpp"
#include "termin/scene/scene_manager.hpp"
#include "termin/render/rendering_manager.hpp"

#include <atomic>
#include <cstdint>
#include <functional>
#include <memory>

namespace termin {

namespace engine_detail {
struct EngineLoopState;
}

// Complete external integration required by EngineCore::run(). Keeping these
// callbacks in one value prevents frontends from exposing a partially attached
// loop client.
struct TERMIN_ENGINE_API EngineLoopClient {
    std::function<void()> poll_events;
    std::function<bool()> should_continue;
    std::function<void()> on_shutdown;
};

// Move-only lifetime handle for an attached EngineLoopClient. Destruction or
// detach() removes the whole client. The weak state reference makes a handle
// harmless when it outlives its EngineCore.
class TERMIN_ENGINE_API EngineLoopClientConnection {
public:
    EngineLoopClientConnection() = default;
    ~EngineLoopClientConnection();

    EngineLoopClientConnection(const EngineLoopClientConnection&) = delete;
    EngineLoopClientConnection& operator=(const EngineLoopClientConnection&) = delete;
    EngineLoopClientConnection(EngineLoopClientConnection&& other) noexcept;
    EngineLoopClientConnection& operator=(EngineLoopClientConnection&& other) noexcept;

    void detach() noexcept;
    bool connected() const noexcept;
    explicit operator bool() const noexcept { return connected(); }

private:
    friend class EngineCore;
    EngineLoopClientConnection(
        std::weak_ptr<engine_detail::EngineLoopState> state,
        std::uint64_t generation
    );

    std::weak_ptr<engine_detail::EngineLoopState> _state;
    std::uint64_t _generation = 0;
};

// EngineCore - owns SceneManager and RenderingManager
class TERMIN_ENGINE_API EngineCore {
public:
    SceneManager scene_manager;
    RenderTopology render_topology;
    RenderingManager rendering_manager;

private:
    std::shared_ptr<engine_detail::EngineLoopState> _loop_state;
    std::atomic<double> _target_fps{60.0};
    bool _profile_ui = false;
    bool _shutdown = false;

public:
    EngineCore();
    ~EngineCore();

    // Disable copy
    EngineCore(const EngineCore&) = delete;
    EngineCore& operator=(const EngineCore&) = delete;

    // --- Configuration ---
    // Zero disables the software frame limiter. Positive values cap the
    // main-loop cadence independently from the presentation mode (VSync).
    void set_target_fps(double fps);
    double target_fps() const { return _target_fps.load(); }

    // When true, run() wraps the poll_events callback in a profiler "UI"
    // section. When false, run() keeps the frame scope but records UI as a
    // muted subtree, so cadence and active-frame timing still cover the whole
    // loop while the section report stays comparable with non-UI hosts.
    void set_profile_ui(bool v) { _profile_ui = v; }
    bool profile_ui() const { return _profile_ui; }

    // Attach the complete external loop integration as one atomic operation.
    // Throws std::invalid_argument for an incomplete client and
    // std::logic_error while another client is attached or the loop is active.
    [[nodiscard]] EngineLoopClientConnection attach_loop_client(EngineLoopClient client);

    // --- Main loop ---
    // Run one frame: scene tick, before_render, RenderingManager render, after_render callback.
    // Returns true if rendering happened.
    bool tick_and_render(double dt);

    // Run blocking main loop. Calls poll_events and tick_and_render, applying
    // target_fps as a software limit when it is greater than zero.
    // Requires an attached loop client. Returns when should_continue returns
    // false or stop() is called.
    void run();

    // Stop the run() loop
    void stop();

    // Check if running
    bool is_running() const;

    // Finalize engine-owned scenes and rendering resources. Hosts must call
    // this after their scene/display integrations are detached and before
    // destroying a graphics device borrowed by RenderEngine. Idempotent;
    // returns false when called while the main loop is still running.
    bool shutdown();
};

} // namespace termin
