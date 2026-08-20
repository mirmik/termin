// engine_core.cpp - EngineCore implementation
#include "termin/engine/engine_core.hpp"
#include "frame_cadence.hpp"
#include "world_context_internal.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <thread>
#include <utility>
#include <vector>

extern "C" {
#include "tc_profiler.h"
#include <tcbase/tc_log.h>
}

namespace termin {

    EngineHostFrameCadence EngineHostFrameCadenceTracker::observe(double start_time_ms,
                                                                  double target_interval_ms) noexcept {
        if (_has_previous && std::abs(target_interval_ms - _target_interval_ms) > 1e-9) {
            _scheduled_start_time_ms = _previous_start_time_ms + target_interval_ms;
        }
        const engine_detail::FrameCadenceObservation observation =
            engine_detail::observe_frame_start(start_time_ms,
                                               _previous_start_time_ms,
                                               _has_previous ? _scheduled_start_time_ms : start_time_ms,
                                               target_interval_ms,
                                               _has_previous);
        _previous_start_time_ms = start_time_ms;
        _scheduled_start_time_ms = observation.next_scheduled_start_ms;
        _target_interval_ms = target_interval_ms;
        _has_previous = true;
        return EngineHostFrameCadence{
            observation.start_time_ms,
            observation.interval_ms,
            observation.target_interval_ms,
            observation.deadline_lateness_ms,
            observation.missed_intervals,
        };
    }

    void EngineHostFrameCadenceTracker::reset() noexcept {
        _previous_start_time_ms = 0.0;
        _scheduled_start_time_ms = 0.0;
        _target_interval_ms = 0.0;
        _has_previous = false;
    }

    EngineHostFrameScope::EngineHostFrameScope(const EngineHostFrameCadence& cadence) noexcept {
        if (!tc_profiler_frame_capture_enabled()) {
            return;
        }
        if (!std::isfinite(cadence.start_time_ms) || cadence.start_time_ms < 0.0 ||
            !std::isfinite(cadence.interval_ms) || cadence.interval_ms < 0.0 ||
            !std::isfinite(cadence.target_interval_ms) || cadence.target_interval_ms < 0.0 ||
            !std::isfinite(cadence.deadline_lateness_ms) || cadence.deadline_lateness_ms < 0.0 ||
            cadence.missed_intervals < 0) {
            tc_log(TC_LOG_ERROR, "[EngineHostFrameScope] Refusing invalid frame cadence");
            return;
        }
        if (tc_profiler_current_frame() != nullptr) {
            tc_log(TC_LOG_ERROR, "[EngineHostFrameScope] Refusing nested host frame scope");
            return;
        }

        const tc_profiler_frame_info frame_info{
            cadence.start_time_ms,
            cadence.interval_ms,
            cadence.target_interval_ms,
            cadence.deadline_lateness_ms,
            cadence.missed_intervals,
        };
        tc_profiler_begin_frame_with_info(&frame_info);
        const tc_frame_profile* current = tc_profiler_current_frame();
        if (!current) {
            tc_log(TC_LOG_ERROR, "[EngineHostFrameScope] Profiler did not open the requested frame");
            return;
        }
        _frame_number = current->frame_number;
    }

    EngineHostFrameScope::~EngineHostFrameScope() {
        finish();
    }

    EngineHostFrameScope::EngineHostFrameScope(EngineHostFrameScope&& other) noexcept
        : _frame_number(std::exchange(other._frame_number, -1)) {}

    EngineHostFrameScope& EngineHostFrameScope::operator=(EngineHostFrameScope&& other) noexcept {
        if (this != &other) {
            finish();
            _frame_number = std::exchange(other._frame_number, -1);
        }
        return *this;
    }

    void EngineHostFrameScope::finish() noexcept {
        if (_frame_number < 0) {
            return;
        }
        const tc_frame_profile* current = tc_profiler_current_frame();
        if (!current) {
            tc_log(TC_LOG_ERROR,
                   "[EngineHostFrameScope] Owned profiler frame %d was ended outside its host scope",
                   _frame_number);
        } else if (current->frame_number != _frame_number) {
            tc_log(TC_LOG_ERROR,
                   "[EngineHostFrameScope] Refusing to close foreign profiler frame %d; expected %d",
                   current->frame_number,
                   _frame_number);
        } else {
            tc_profiler_end_frame();
        }
        _frame_number = -1;
    }

    namespace engine_detail {

        struct EngineLoopState {
            mutable std::mutex mutex;
            std::optional<EngineLoopClient> client;
            std::uint64_t generation = 0;
            std::atomic<bool> running{false};
            bool polling = false;
            std::thread::id polling_thread;
        };

        class EngineLoopPollScope {
        public:
            explicit EngineLoopPollScope(EngineLoopState& state) noexcept
                : _state(state) {
                std::lock_guard lock(_state.mutex);
                _state.polling = true;
                _state.polling_thread = std::this_thread::get_id();
            }

            ~EngineLoopPollScope() {
                std::lock_guard lock(_state.mutex);
                _state.polling = false;
                _state.polling_thread = {};
            }

            EngineLoopPollScope(const EngineLoopPollScope&) = delete;
            EngineLoopPollScope& operator=(const EngineLoopPollScope&) = delete;

        private:
            EngineLoopState& _state;
        };

        struct EngineFrameCompletionState {
            mutable std::mutex mutex;
            std::shared_ptr<std::function<void()>> callback;
            std::uint64_t generation = 0;
        };

        class RuntimeSession {
        public:
            RuntimeSession(EngineCore& engine, WorldControllerInstance controller)
                : _engine(engine),
                  _controller(std::move(controller)),
                  _context(create_world_context(_controller.native_handle())) {}

            ~RuntimeSession() {
                if (_active && !end()) {
                    tc_log(TC_LOG_ERROR, "[RuntimeSession] Failed to end during destruction");
                }
                invalidate_world_context(_context);
                tc_world_context_release(_context);
            }

            RuntimeSession(const RuntimeSession&) = delete;
            RuntimeSession& operator=(const RuntimeSession&) = delete;

            bool start() {
                if (_active) {
                    tc_log(TC_LOG_ERROR, "[RuntimeSession] Refusing repeated start");
                    return false;
                }
                if (!_context) {
                    tc_log(TC_LOG_ERROR, "[RuntimeSession] Cannot start without a WorldContext");
                    _controller.reset();
                    return false;
                }
                if (_controller) {
                    char message[1024] = {};
                    tc_world_controller_error_v1 error{
                        sizeof(tc_world_controller_error_v1), message, sizeof(message)};
                    if (!tc_world_controller_instance_start(
                            _controller.native_handle(), _context, &error)) {
                        tc_log(TC_LOG_ERROR,
                               "[RuntimeSession] WorldController start failed: %s",
                               message[0] ? message : "unknown lifecycle failure");
                        _controller.reset();
                        invalidate_world_context(_context);
                        return false;
                    }
                }
                _active = true;
                return true;
            }

            bool end() {
                if (!_active) {
                    tc_log(TC_LOG_ERROR, "[RuntimeSession] Refusing end without an active session");
                    return false;
                }
                bool clean = true;
                release_primary_scene();
                for (tc_scene_handle scene : _bound_scenes) {
                    if (!unbind_world_context_scene(_context, scene)) {
                        clean = false;
                    }
                }
                _bound_scenes.clear();
                if (_controller) {
                    char message[1024] = {};
                    tc_world_controller_error_v1 error{
                        sizeof(tc_world_controller_error_v1), message, sizeof(message)};
                    if (!tc_world_controller_instance_stop(_controller.native_handle(), &error)) {
                        tc_log(TC_LOG_ERROR,
                               "[RuntimeSession] WorldController stop failed: %s",
                               message[0] ? message : "unknown lifecycle failure");
                        clean = false;
                    }
                }
                invalidate_world_context(_context);
                if (_controller) {
                    if (!_controller.reset()) {
                        clean = false;
                    }
                }
                _active = false;
                return clean;
            }

            bool bind_scene(tc_scene_handle scene) {
                if (!_active) {
                    tc_log(TC_LOG_ERROR, "[RuntimeSession] Cannot bind a scene before session start");
                    return false;
                }
                const auto existing = std::find_if(
                    _bound_scenes.begin(), _bound_scenes.end(), [scene](tc_scene_handle bound) {
                        return tc_scene_handle_eq(bound, scene);
                    });
                if (existing != _bound_scenes.end()) {
                    return true;
                }
                if (!bind_world_context_scene(_context, scene)) {
                    return false;
                }
                _bound_scenes.push_back(scene);
                return true;
            }

            bool unbind_scene(tc_scene_handle scene) {
                const auto existing = std::find_if(
                    _bound_scenes.begin(), _bound_scenes.end(), [scene](tc_scene_handle bound) {
                        return tc_scene_handle_eq(bound, scene);
                    });
                if (existing == _bound_scenes.end()) {
                    tc_log(TC_LOG_ERROR, "[RuntimeSession] Scene is not bound to this session");
                    return false;
                }
                if (tc_scene_handle_eq(tc_world_context_primary_scene(_context), scene)) {
                    tc_log(TC_LOG_ERROR,
                           "[RuntimeSession] Cannot unbind the primary scene; switch it or end the session first");
                    return false;
                }
                clear_world_context_scene_references(_context, scene);
                if (!unbind_world_context_scene(_context, scene)) {
                    return false;
                }
                _bound_scenes.erase(existing);
                return true;
            }

            void on_scene_destroying(tc_scene_handle scene) noexcept {
                const auto existing = std::find_if(
                    _bound_scenes.begin(), _bound_scenes.end(), [scene](tc_scene_handle bound) {
                        return tc_scene_handle_eq(bound, scene);
                    });
                if (existing == _bound_scenes.end()) {
                    return;
                }
                clear_world_context_scene_references(_context, scene);
                if (!unbind_world_context_scene(_context, scene)) {
                    tc_log(TC_LOG_ERROR, "[RuntimeSession] Failed to unbind a scene before destruction");
                }
                _bound_scenes.erase(existing);
            }

            void process_primary_scene_request() {
                const tc_scene_handle candidate = take_world_context_primary_request(_context);
                if (!tc_scene_handle_valid(candidate)) {
                    return;
                }
                if (!scene_is_transition_candidate(candidate)) {
                    tc_log(TC_LOG_ERROR,
                           "[RuntimeSession] Dropped primary scene request: target must remain registered "
                           "as RUNTIME, bound to this session, inactive and render-detached");
                    return;
                }

                const tc_scene_handle previous = tc_world_context_primary_scene(_context);
                if (tc_scene_handle_eq(previous, candidate)) {
                    return;
                }

                tc_scene_mode active_mode = TC_SCENE_MODE_PLAY;
                if (tc_scene_handle_valid(previous)) {
                    if (!scene_is_bound(previous) || !scene_is_registered_runtime(previous) ||
                        !_engine.render_topology.is_attached(previous)) {
                        tc_log(TC_LOG_ERROR,
                               "[RuntimeSession] Dropped primary scene request: current primary invariant is broken");
                        return;
                    }
                    active_mode = tc_scene_get_mode(previous);
                    if (active_mode != TC_SCENE_MODE_PLAY && active_mode != TC_SCENE_MODE_STOP) {
                        tc_log(TC_LOG_ERROR,
                               "[RuntimeSession] Dropped primary scene request: current primary is not active");
                        return;
                    }
                }

                try {
                    (void)_engine.rendering_manager.attach_scene_full(candidate);
                } catch (...) {
                    if (tc_scene_alive(candidate)) {
                        _engine.rendering_manager.detach_scene_full(candidate);
                    }
                    throw;
                }
                if (!_engine.render_topology.is_attached(candidate)) {
                    tc_log(TC_LOG_ERROR,
                           "[RuntimeSession] Primary scene render preparation failed; keeping the current primary");
                    return;
                }
                if (!scene_is_prepared_candidate(candidate)) {
                    tc_log(TC_LOG_ERROR,
                           "[RuntimeSession] Candidate changed during render preparation; rolling it back");
                    cleanup_candidate(candidate);
                    return;
                }

                if (tc_scene_handle_valid(previous)) {
                    tc_scene_set_mode(previous, TC_SCENE_MODE_INACTIVE);
                    if (tc_scene_alive(previous) && _engine.render_topology.is_attached(previous)) {
                        _engine.rendering_manager.detach_scene_full(previous);
                    }
                }

                if (!scene_is_prepared_candidate(candidate)) {
                    tc_log(TC_LOG_ERROR,
                           "[RuntimeSession] Candidate changed while deactivating the old primary; rolling back");
                    cleanup_candidate(candidate);
                    restore_previous_primary(previous, active_mode);
                    return;
                }
                if (!publish_world_context_primary_scene(_context, candidate)) {
                    tc_log(TC_LOG_ERROR,
                           "[RuntimeSession] Failed to publish the prepared primary scene; rolling back");
                    cleanup_candidate(candidate);
                    restore_previous_primary(previous, active_mode);
                    return;
                }

                tc_scene_set_mode(candidate, active_mode);
                if (!tc_scene_alive(candidate) ||
                    !tc_scene_handle_eq(tc_world_context_primary_scene(_context), candidate) ||
                    !_engine.render_topology.is_attached(candidate) ||
                    tc_scene_get_mode(candidate) != active_mode) {
                    tc_log(TC_LOG_ERROR,
                           "[RuntimeSession] Primary scene activation violated transaction invariants; rolling back");
                    cleanup_candidate(candidate);
                    restore_previous_primary(previous, active_mode);
                    return;
                }

                _engine.scene_manager.request_render();
            }

        private:
            bool scene_is_bound(tc_scene_handle scene) const noexcept {
                const auto existing = std::find_if(
                    _bound_scenes.begin(), _bound_scenes.end(), [scene](tc_scene_handle bound) {
                        return tc_scene_handle_eq(bound, scene);
                    });
                if (existing == _bound_scenes.end()) {
                    return false;
                }
                tc_world_context* context = tc_world_context_acquire_from_scene(scene);
                const bool matches = context == _context;
                tc_world_context_release(context);
                return matches;
            }

            bool scene_is_transition_candidate(tc_scene_handle scene) const noexcept {
                return scene_is_candidate_identity(scene) &&
                       !_engine.render_topology.is_attached(scene);
            }

            bool scene_is_prepared_candidate(tc_scene_handle scene) const noexcept {
                return scene_is_candidate_identity(scene) &&
                       _engine.render_topology.is_attached(scene);
            }

            bool scene_is_candidate_identity(tc_scene_handle scene) const noexcept {
                return tc_scene_alive(scene) && scene_is_bound(scene) &&
                       scene_is_registered_runtime(scene) &&
                       tc_scene_get_mode(scene) == TC_SCENE_MODE_INACTIVE;
            }

            bool scene_is_registered_runtime(tc_scene_handle scene) const noexcept {
                const std::optional<SceneKey> key = _engine.scene_manager.key_of(scene);
                return key.has_value() && key->role == SceneRole::Runtime;
            }

            void cleanup_candidate(tc_scene_handle scene) {
                if (!tc_scene_alive(scene)) {
                    return;
                }
                if (tc_scene_get_mode(scene) != TC_SCENE_MODE_INACTIVE) {
                    tc_scene_set_mode(scene, TC_SCENE_MODE_INACTIVE);
                }
                if (_engine.render_topology.is_attached(scene)) {
                    _engine.rendering_manager.detach_scene_full(scene);
                }
                clear_world_context_scene_references(_context, scene);
            }

            bool restore_previous_primary(tc_scene_handle previous, tc_scene_mode mode) noexcept {
                if (!tc_scene_handle_valid(previous)) {
                    (void)publish_world_context_primary_scene(_context, TC_SCENE_HANDLE_INVALID);
                    return true;
                }
                if (!tc_scene_alive(previous) || !scene_is_bound(previous) ||
                    !scene_is_registered_runtime(previous)) {
                    tc_log(TC_LOG_ERROR,
                           "[RuntimeSession] Cannot roll back: the previous primary scene is no longer available");
                    (void)publish_world_context_primary_scene(_context, TC_SCENE_HANDLE_INVALID);
                    return false;
                }
                if (!_engine.render_topology.is_attached(previous)) {
                    try {
                        (void)_engine.rendering_manager.attach_scene_full(previous);
                    } catch (...) {
                        tc_log(TC_LOG_ERROR,
                               "[RuntimeSession] Exception while restoring the previous primary rendering");
                        (void)publish_world_context_primary_scene(_context, TC_SCENE_HANDLE_INVALID);
                        return false;
                    }
                }
                if (!_engine.render_topology.is_attached(previous) ||
                    !publish_world_context_primary_scene(_context, previous)) {
                    tc_log(TC_LOG_ERROR,
                           "[RuntimeSession] Failed to restore the previous primary render attachment");
                    (void)publish_world_context_primary_scene(_context, TC_SCENE_HANDLE_INVALID);
                    return false;
                }
                tc_scene_set_mode(previous, mode);
                _engine.scene_manager.request_render();
                return tc_scene_get_mode(previous) == mode;
            }

            void release_primary_scene() {
                (void)take_world_context_primary_request(_context);
                const tc_scene_handle primary = tc_world_context_primary_scene(_context);
                if (!tc_scene_handle_valid(primary)) {
                    return;
                }
                if (tc_scene_alive(primary)) {
                    tc_scene_set_mode(primary, TC_SCENE_MODE_INACTIVE);
                    if (_engine.render_topology.is_attached(primary)) {
                        _engine.rendering_manager.detach_scene_full(primary);
                    }
                }
                (void)publish_world_context_primary_scene(_context, TC_SCENE_HANDLE_INVALID);
            }

            EngineCore& _engine;
            WorldControllerInstance _controller;
            tc_world_context* _context = nullptr;
            std::vector<tc_scene_handle> _bound_scenes;
            bool _active = false;
        };

    } // namespace engine_detail

    EngineLoopClientConnection::EngineLoopClientConnection(std::weak_ptr<engine_detail::EngineLoopState> state,
                                                           std::uint64_t generation)
        : _state(std::move(state)),
          _generation(generation) {}

    EngineLoopClientConnection::~EngineLoopClientConnection() {
        detach();
    }

    EngineLoopClientConnection::EngineLoopClientConnection(EngineLoopClientConnection&& other) noexcept
        : _state(std::move(other._state)),
          _generation(std::exchange(other._generation, 0)) {}

    EngineLoopClientConnection& EngineLoopClientConnection::operator=(EngineLoopClientConnection&& other) noexcept {
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

    EngineFrameCompletionConnection::EngineFrameCompletionConnection(
        std::weak_ptr<engine_detail::EngineFrameCompletionState> state, std::uint64_t generation)
        : _state(std::move(state)),
          _generation(generation) {}

    EngineFrameCompletionConnection::~EngineFrameCompletionConnection() {
        detach();
    }

    EngineFrameCompletionConnection::EngineFrameCompletionConnection(EngineFrameCompletionConnection&& other) noexcept
        : _state(std::move(other._state)),
          _generation(std::exchange(other._generation, 0)) {}

    EngineFrameCompletionConnection&
    EngineFrameCompletionConnection::operator=(EngineFrameCompletionConnection&& other) noexcept {
        if (this != &other) {
            detach();
            _state = std::move(other._state);
            _generation = std::exchange(other._generation, 0);
        }
        return *this;
    }

    void EngineFrameCompletionConnection::detach() noexcept {
        if (_generation == 0) {
            return;
        }
        if (const auto state = _state.lock()) {
            std::lock_guard lock(state->mutex);
            if (state->callback && state->generation == _generation) {
                state->callback.reset();
            }
        }
        _state.reset();
        _generation = 0;
    }

    bool EngineFrameCompletionConnection::connected() const noexcept {
        if (_generation == 0) {
            return false;
        }
        const auto state = _state.lock();
        if (!state) {
            return false;
        }
        std::lock_guard lock(state->mutex);
        return state->callback && state->generation == _generation;
    }

    EngineCore::EngineCore()
        : rendering_manager(render_topology),
          _loop_state(std::make_shared<engine_detail::EngineLoopState>()),
          _frame_completion_state(std::make_shared<engine_detail::EngineFrameCompletionState>()) {
        if (!tc_world_controller_registry_init()) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Failed to initialize the WorldController registry root");
        }
        if (!tc_world_context_scene_extension_init()) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Failed to register the WorldContext scene extension");
        }
        scene_manager.set_before_scene_destroy_guard([this](tc_scene_handle scene) {
            if (_runtime_session) {
                _runtime_session->on_scene_destroying(scene);
            }
            if (!render_topology.is_attached(scene) && render_topology.render_targets(scene).empty() &&
                render_topology.viewports(scene).empty()) {
                return;
            }
            tc_log(TC_LOG_ERROR,
                   "[EngineCore] Scene destruction requested with live render attachments; forcing detach");
            rendering_manager.detach_scene_full(scene, true);
            if (render_topology.is_attached(scene) || !render_topology.render_targets(scene).empty() ||
                !render_topology.viewports(scene).empty()) {
                tc_log(TC_LOG_ERROR, "[EngineCore] Mandatory render detach left live scene topology");
            }
        });
        tc_log(TC_LOG_INFO, "[EngineCore] Created");
    }

    EngineCore::~EngineCore() {
        stop();
        if (!shutdown()) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Failed to shut down during destruction");
        }
    }

    bool EngineCore::shutdown() {
        if (_shutdown) {
            return true;
        }
        if (is_running()) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Refusing shutdown while the main loop is running");
            return false;
        }
        if (_session_operation != SessionOperation::Idle) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Refusing shutdown during RuntimeSession lifecycle callback");
            return false;
        }

        bool clean = true;
        if (_runtime_session) {
            clean = end_session();
            if (_runtime_session) {
                tc_log(TC_LOG_ERROR,
                       "[EngineCore] Refusing resource shutdown while RuntimeSession teardown is reentrant");
                return false;
            }
        }

        // Scene-owned render objects must be detached while scene handles and the
        // scene runtime are still alive. The frontend has already released its
        // integrations, but this central pass is the final ownership backstop.
        const std::vector<tc_scene_handle> attached_scenes(render_topology.attached_scenes().begin(),
                                                           render_topology.attached_scenes().end());
        for (tc_scene_handle scene : attached_scenes) {
            rendering_manager.detach_scene_full(scene, true);
        }
        scene_manager.close_all_scenes();
        rendering_manager.shutdown();
        _shutdown = true;
        tc_log(TC_LOG_INFO, "[EngineCore] Shutdown complete");
        return clean;
    }

    bool EngineCore::begin_session() {
        WorldControllerInstance controller;
        return begin_session_owned(std::move(controller));
    }

    bool EngineCore::begin_session(WorldControllerInstance&& controller) {
        if (!controller) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Refusing an invalid or already-consumed WorldController owner");
            return false;
        }
        return begin_session_owned(std::move(controller));
    }

    bool EngineCore::begin_session_owned(WorldControllerInstance&& controller) {
        if (_shutdown) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Cannot begin RuntimeSession after shutdown");
            return false;
        }
        if (!session_mutation_is_safe()) {
            tc_log(TC_LOG_ERROR,
                   "[EngineCore] Cannot begin RuntimeSession outside the owning loop's poll callback");
            return false;
        }
        if (_session_operation != SessionOperation::Idle) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Refusing reentrant RuntimeSession begin");
            return false;
        }
        if (_runtime_session) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Refusing a second active RuntimeSession");
            return false;
        }
        if (controller && controller.state() != TC_WORLD_CONTROLLER_STATE_CREATED) {
            tc_log(TC_LOG_ERROR, "[EngineCore] WorldController owner is not in CREATED state");
            return false;
        }

        _session_operation = SessionOperation::Beginning;
        try {
            auto candidate =
                std::make_unique<engine_detail::RuntimeSession>(*this, std::move(controller));
            if (!candidate->start()) {
                _session_operation = SessionOperation::Idle;
                return false;
            }
            _runtime_session = std::move(candidate);
            _session_operation = SessionOperation::Idle;
            tc_log(TC_LOG_INFO, "[EngineCore] RuntimeSession started");
            return true;
        } catch (const std::exception& exception) {
            _session_operation = SessionOperation::Idle;
            tc_log(TC_LOG_ERROR,
                   "[EngineCore] Failed to allocate RuntimeSession: %s",
                   exception.what());
        } catch (...) {
            _session_operation = SessionOperation::Idle;
            tc_log(TC_LOG_ERROR, "[EngineCore] Failed to allocate RuntimeSession with unknown exception");
        }
        return false;
    }

    bool EngineCore::end_session() {
        if (_session_operation != SessionOperation::Idle) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Refusing reentrant RuntimeSession end");
            return false;
        }
        if (!_runtime_session) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Refusing RuntimeSession end without an active session");
            return false;
        }
        if (!session_mutation_is_safe()) {
            tc_log(TC_LOG_ERROR,
                   "[EngineCore] Cannot end RuntimeSession outside the owning loop's poll callback");
            return false;
        }

        _session_operation = SessionOperation::Ending;
        const bool clean = _runtime_session->end();
        _runtime_session.reset();
        _session_operation = SessionOperation::Idle;
        if (clean) {
            tc_log(TC_LOG_INFO, "[EngineCore] RuntimeSession ended");
        } else {
            tc_log(TC_LOG_ERROR, "[EngineCore] RuntimeSession ended with lifecycle failures");
        }
        return clean;
    }

    bool EngineCore::session_mutation_is_safe() const noexcept {
        if (!is_running()) {
            return true;
        }
        std::lock_guard lock(_loop_state->mutex);
        return _loop_state->polling &&
               _loop_state->polling_thread == std::this_thread::get_id();
    }

    bool EngineCore::bind_runtime_scene(tc_scene_handle scene) {
        if (_session_operation != SessionOperation::Idle) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Refusing scene bind during RuntimeSession lifecycle callback");
            return false;
        }
        if (!_runtime_session) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Cannot bind a runtime scene without an active RuntimeSession");
            return false;
        }
        const std::optional<SceneKey> key = scene_manager.key_of(scene);
        if (!key.has_value()) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Runtime scene must be live and registered with this SceneManager");
            return false;
        }
        if (key->role != SceneRole::Runtime) {
            tc_log(TC_LOG_ERROR,
                   "[EngineCore] Cannot bind AUTHORING scene '%s' to RuntimeSession; RUNTIME role is required",
                   key->identity.c_str());
            return false;
        }
        return _runtime_session->bind_scene(scene);
    }

    bool EngineCore::unbind_runtime_scene(tc_scene_handle scene) {
        if (_session_operation != SessionOperation::Idle) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Refusing scene unbind during RuntimeSession lifecycle callback");
            return false;
        }
        if (!_runtime_session) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Cannot unbind a runtime scene without an active RuntimeSession");
            return false;
        }
        return _runtime_session->unbind_scene(scene);
    }

    EngineLoopClientConnection EngineCore::attach_loop_client(EngineLoopClient client) {
        if (_shutdown) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Cannot attach a loop client after shutdown");
            throw std::logic_error("cannot attach a loop client after EngineCore shutdown");
        }
        if (!client.poll_events || !client.should_continue || !client.on_shutdown) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Refusing incomplete loop client; all callbacks are required");
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

    EngineFrameCompletionConnection EngineCore::attach_frame_completion_callback(std::function<void()> callback) {
        if (_shutdown) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Cannot attach a frame completion callback after shutdown");
            throw std::logic_error("cannot attach a frame completion callback after EngineCore shutdown");
        }
        if (!callback) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Refusing empty frame completion callback");
            throw std::invalid_argument("frame completion callback must not be empty");
        }
        if (is_running()) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Cannot attach a frame completion callback while run() is active");
            throw std::logic_error("cannot attach a frame completion callback while EngineCore is running");
        }

        std::lock_guard lock(_frame_completion_state->mutex);
        if (_frame_completion_state->callback) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Refusing second frame completion callback");
            throw std::logic_error("EngineCore already has a frame completion callback");
        }
        ++_frame_completion_state->generation;
        _frame_completion_state->callback = std::make_shared<std::function<void()>>(std::move(callback));
        return EngineFrameCompletionConnection(_frame_completion_state, _frame_completion_state->generation);
    }

    void EngineCore::stop() {
        _loop_state->running.store(false);
    }

    bool EngineCore::is_running() const {
        return _loop_state->running.load();
    }

    void EngineCore::set_target_fps(double fps) {
        if (!std::isfinite(fps) || fps < 0.0) {
            tc_log(TC_LOG_ERROR,
                   "[EngineCore] Invalid target FPS %.3f; expected zero (unlimited) or a positive value",
                   fps);
            throw std::invalid_argument("target FPS must be zero (unlimited) or a positive finite value");
        }
        _target_fps.store(fps);
    }

    bool EngineCore::tick(double dt) {
        if (_shutdown) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Cannot tick after shutdown");
            return false;
        }
        bool profile = tc_profiler_enabled();

        if (_runtime_session) {
            if (_session_operation != SessionOperation::Idle) {
                tc_log(TC_LOG_ERROR,
                       "[EngineCore] Cannot process a primary scene request during RuntimeSession lifecycle work");
            } else {
                _session_operation = SessionOperation::SwitchingPrimary;
                try {
                    _runtime_session->process_primary_scene_request();
                } catch (const std::exception& exception) {
                    tc_log(TC_LOG_ERROR,
                           "[EngineCore] Primary scene transaction raised an exception: %s",
                           exception.what());
                } catch (...) {
                    tc_log(TC_LOG_ERROR,
                           "[EngineCore] Primary scene transaction raised an unknown exception");
                }
                _session_operation = SessionOperation::Idle;
            }
        }

        if (profile)
            tc_profiler_begin_section("SceneManager Tick");
        const bool should_render = scene_manager.tick(dt);
        if (profile)
            tc_profiler_end_section();

        return should_render;
    }

    bool EngineCore::tick_and_render(double dt) {
        // Frame scope is owned by run() — tick_and_render only opens sections
        // inside the already-open frame. When called standalone (outside run),
        // sections are no-ops because current_frame is NULL.
        const bool should_render = tick(dt);
        if (_shutdown) {
            return false;
        }
        const bool profile = tc_profiler_enabled();

        if (should_render) {
            if (profile)
                tc_profiler_begin_section("SceneManager Render");
            rendering_manager.render_all(true);
            if (profile)
                tc_profiler_end_section();

            if (profile)
                tc_profiler_begin_section("SceneManager After Render");
            scene_manager.invoke_after_render();
            if (profile)
                tc_profiler_end_section();
        }

        return should_render;
    }

    void EngineCore::run() {
        if (_shutdown) {
            tc_log(TC_LOG_ERROR, "[EngineCore] Cannot run after shutdown");
            throw std::logic_error("cannot run EngineCore after shutdown");
        }
        EngineLoopClient loop_client;
        std::shared_ptr<std::function<void()>> frame_completion_callback;
        {
            std::lock_guard lock(_loop_state->mutex);
            if (_loop_state->running.load()) {
                tc_log(TC_LOG_ERROR, "[EngineCore] Refusing nested run() call");
                throw std::logic_error("EngineCore::run() is already active");
            }
            if (!_loop_state->client) {
                tc_log(TC_LOG_ERROR, "[EngineCore] Refusing run() without an attached loop client");
                throw std::logic_error("EngineCore::run() requires an attached loop client");
            }
            loop_client = *_loop_state->client;
            _loop_state->running.store(true);
        }
        {
            std::lock_guard lock(_frame_completion_state->mutex);
            frame_completion_callback = _frame_completion_state->callback;
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
            const double target_interval_ms = active_target_fps > 0.0 ? 1000.0 / active_target_fps : 0.0;
            double dt = std::chrono::duration<double>(frame_start - last_time).count();
            const double start_time_ms =
                std::chrono::duration<double, std::milli>(frame_start.time_since_epoch()).count();
            const double previous_start_time_ms =
                std::chrono::duration<double, std::milli>(last_time.time_since_epoch()).count();
            const double scheduled_start_time_ms =
                std::chrono::duration<double, std::milli>(scheduled_frame_time.time_since_epoch()).count();
            const engine_detail::FrameCadenceObservation cadence = engine_detail::observe_frame_start(
                start_time_ms, previous_start_time_ms, scheduled_start_time_ms, target_interval_ms, has_previous_frame);
            if (!has_previous_frame || frame_start > scheduled_frame_time) {
                scheduled_frame_time = frame_start;
            }
            last_time = frame_start;
            has_previous_frame = true;

            {
                EngineHostFrameScope frame_scope(EngineHostFrameCadence{
                    cadence.start_time_ms,
                    cadence.interval_ms,
                    cadence.target_interval_ms,
                    cadence.deadline_lateness_ms,
                    cadence.missed_intervals,
                });
                const bool profile = tc_profiler_enabled();

                // Always wrap the UI callback in a section so the sub-sections
                // the callback opens (Events, Render Compose, …) are nested
                // under a single root instead of bubbling up as siblings of
                // SceneManager Render. When profile_ui is off the wrap is
                // *muted* — the section and everything inside it doesn't
                // record; callees don't need to know about the flag.
                if (profile) {
                    if (_profile_ui)
                        tc_profiler_begin_section("UI");
                    else
                        tc_profiler_begin_section_muted("UI");
                }
                if (loop_client.poll_events) {
                    engine_detail::EngineLoopPollScope poll_scope(*_loop_state);
                    loop_client.poll_events();
                }
                if (profile)
                    tc_profiler_end_section();

                // Check if should continue
                if (loop_client.should_continue && !loop_client.should_continue()) {
                    _loop_state->running.store(false);
                    break;
                }

                // Tick and render — opens its own sections inside the frame
                // scope owned by this block.
                tick_and_render(dt);
            }

            if (frame_completion_callback) {
                (*frame_completion_callback)();
            }

            if (active_target_fps > 0.0) {
                // Frame limiting with sleep_until for stable pacing. Keep the
                // expected start until the next iteration observes it. A late
                // frame is resynchronized above only after its lateness has been
                // recorded, so scheduler catch-up cannot erase hitch evidence.
                const auto frame_duration =
                    std::chrono::duration_cast<duration>(std::chrono::duration<double>(1.0 / active_target_fps));
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
