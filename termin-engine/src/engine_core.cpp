// engine_core.cpp - EngineCore implementation
#include "termin/engine/engine_core.hpp"
#include "frame_cadence.hpp"

#include <chrono>
#include <cmath>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <thread>
#include <utility>

extern "C" {
#include <tcbase/tc_log.h>
#include "tc_profiler.h"
}

namespace termin {

namespace engine_detail {

struct EngineLoopState {
    mutable std::mutex mutex;
    std::optional<EngineLoopClient> client;
    std::uint64_t generation = 0;
    std::atomic<bool> running{false};
};

} // namespace engine_detail

EngineLoopClientConnection::EngineLoopClientConnection(
    std::weak_ptr<engine_detail::EngineLoopState> state,
    std::uint64_t generation
)
    : _state(std::move(state)), _generation(generation) {}

EngineLoopClientConnection::~EngineLoopClientConnection() {
    detach();
}

EngineLoopClientConnection::EngineLoopClientConnection(
    EngineLoopClientConnection&& other
) noexcept
    : _state(std::move(other._state)),
      _generation(std::exchange(other._generation, 0)) {}

EngineLoopClientConnection& EngineLoopClientConnection::operator=(
    EngineLoopClientConnection&& other
) noexcept {
    if (this != &other) {
        detach();
        _state = std::move(other._state);
        _generation = std::exchange(other._generation, 0);
    }
    return *this;
}

void EngineLoopClientConnection::detach() noexcept {
    if (_generation == 0) {
        return;
    }
    if (const auto state = _state.lock()) {
        std::lock_guard lock(state->mutex);
        if (state->client && state->generation == _generation) {
            state->running.store(false);
            state->client.reset();
        }
    }
    _state.reset();
    _generation = 0;
}

bool EngineLoopClientConnection::connected() const noexcept {
    if (_generation == 0) {
        return false;
    }
    const auto state = _state.lock();
    if (!state) {
        return false;
    }
    std::lock_guard lock(state->mutex);
    return state->client.has_value() && state->generation == _generation;
}

EngineCore::EngineCore()
    : rendering_manager(render_topology),
      _loop_state(std::make_shared<engine_detail::EngineLoopState>()) {
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
    stop();
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
    tc_log(TC_LOG_INFO, "[EngineCore] Destroyed");
}

EngineLoopClientConnection EngineCore::attach_loop_client(EngineLoopClient client) {
    if (!client.poll_events || !client.should_continue || !client.on_shutdown) {
        tc_log(
            TC_LOG_ERROR,
            "[EngineCore] Refusing incomplete loop client; all callbacks are required"
        );
        throw std::invalid_argument("EngineLoopClient requires all callbacks");
    }

    std::lock_guard lock(_loop_state->mutex);
    if (_loop_state->running.load()) {
        tc_log(TC_LOG_ERROR, "[EngineCore] Cannot attach loop client while run() is active");
        throw std::logic_error("cannot attach loop client while EngineCore is running");
    }
    if (_loop_state->client) {
        tc_log(TC_LOG_ERROR, "[EngineCore] Refusing second active loop client");
        throw std::logic_error("EngineCore already has an active loop client");
    }

    ++_loop_state->generation;
    _loop_state->client.emplace(std::move(client));
    return EngineLoopClientConnection(_loop_state, _loop_state->generation);
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

void EngineCore::stop() {
    _loop_state->running.store(false);
}

bool EngineCore::is_running() const {
    return _loop_state->running.load();
}

void EngineCore::set_target_fps(double fps) {
    if (!std::isfinite(fps) || fps < 0.0) {
        tc_log(
            TC_LOG_ERROR,
            "[EngineCore] Invalid target FPS %.3f; expected zero (unlimited) or a positive value",
            fps
        );
        throw std::invalid_argument(
            "target FPS must be zero (unlimited) or a positive finite value"
        );
    }
    _target_fps.store(fps);
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
    EngineLoopClient loop_client;
    {
        std::lock_guard lock(_loop_state->mutex);
        if (_loop_state->running.load()) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Refusing nested run() call");
            throw std::logic_error("EngineCore::run() is already active");
        }
        _loop_state->running.store(true);
        if (_loop_state->client) {
            loop_client = *_loop_state->client;
        } else {
            // Temporary compatibility path for frontends not yet migrated to
            // attach_loop_client(). Remove together with the legacy setters.
            loop_client.poll_events = _poll_events_callback;
            loop_client.should_continue = _should_continue_callback;
            loop_client.on_shutdown = _on_shutdown_callback;
        }
    }

    using clock = std::chrono::steady_clock;
    using duration = clock::duration;

    auto scheduled_frame_time = clock::now();
    auto last_time = scheduled_frame_time;
    bool has_previous_frame = false;
    double active_target_fps = _target_fps.load();

    if (active_target_fps > 0.0) {
        tc_log(TC_LOG_INFO, "[EngineCore] Starting main loop with %.1f FPS limit", active_target_fps);
    } else {
        tc_log(TC_LOG_INFO, "[EngineCore] Starting main loop without FPS limit");
    }

    while (_loop_state->running.load()) {
        auto frame_start = clock::now();
        const double configured_target_fps = _target_fps.load();
        if (configured_target_fps != active_target_fps) {
            active_target_fps = configured_target_fps;
            scheduled_frame_time = frame_start;
            if (active_target_fps > 0.0) {
                tc_log(TC_LOG_INFO, "[EngineCore] FPS limit changed to %.1f", active_target_fps);
            } else {
                tc_log(TC_LOG_INFO, "[EngineCore] FPS limit disabled");
            }
        }
        const double target_interval_ms = active_target_fps > 0.0
            ? 1000.0 / active_target_fps
            : 0.0;
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
        if (loop_client.poll_events) loop_client.poll_events();
        if (profile) tc_profiler_end_section();

        // Check if should continue
        if (loop_client.should_continue && !loop_client.should_continue()) {
            if (capture_frame) tc_profiler_end_frame();
            _loop_state->running.store(false);
            break;
        }

        // Tick and render — opens its own sections inside the frame
        // scope owned by this function.
        tick_and_render(dt);

        if (capture_frame) tc_profiler_end_frame();

        if (active_target_fps > 0.0) {
            // Frame limiting with sleep_until for stable pacing. Keep the
            // expected start until the next iteration observes it. A late
            // frame is resynchronized above only after its lateness has been
            // recorded, so scheduler catch-up cannot erase hitch evidence.
            const auto frame_duration = std::chrono::duration_cast<duration>(
                std::chrono::duration<double>(1.0 / active_target_fps)
            );
            scheduled_frame_time += frame_duration;
            std::this_thread::sleep_until(scheduled_frame_time);
        } else {
            // With no software limit, presentation (if synchronized) or the
            // actual workload determines cadence. Keep profiler deadlines
            // neutral instead of accumulating artificial lateness.
            scheduled_frame_time = clock::now();
        }
    }

    tc_log(TC_LOG_INFO, "[EngineCore] Main loop stopped");

    // Shutdown callback (cleanup)
    if (loop_client.on_shutdown) {
        loop_client.on_shutdown();
    }
}

} // namespace termin
