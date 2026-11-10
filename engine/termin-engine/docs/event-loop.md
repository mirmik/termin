# Event-driven engine hosts

`EngineCore::run()` supports two explicit host contracts. A three-callback
`EngineLoopClient` is frame-driven (standalone player). A planned host supplies
all of `plan_work(now)`, `wait_until(deadline)` and `wake()` in addition to
`poll_events`, `should_continue` and `on_shutdown`. Partial planning contracts
are rejected. SDL and other platform wait implementations belong to the host,
not the engine.

`EngineLoopPlan` separates service backlog (`immediate_work`), a requested host
frame (`frame_requested`), ongoing host animation (`continuous_update`) and the
next service deadline (`next_deadline`, optional monotonic seconds). A service
wake only polls work; it neither advances simulation nor creates a profiler
frame. Service deadlines must be cleared or advanced when serviced. Pending
bounded queues keep `immediate_work` set until drained.

The host handles events/queues in `poll_events`, advances camera animation in
`before_frame(dt)` and composes requested UI in `after_frame()`. The engine
rechecks scene demand after `before_frame`, so a camera mutation is rendered
in that frame. `last_frame_rendered` distinguishes scene rendering from UI-only
composition (for example, presenting the profiler itself).

Frame limits apply only to requested work. Input and service queues can be
serviced before the next permitted frame; they cannot bypass the frame limit.
Unlimited permits immediate frames when there is demand and indefinite waiting
otherwise. Host waits must preserve wake notifications across check-to-wait,
handle all windows and release the Python GIL while blocking. `stop()`, pacing
changes, scene invalidation and runtime scene-transition requests notify `wake`.
Wake handles must remain safe through detach and shutdown.

Scene scheduling is queried without consuming requests via
`SceneManager::work_state()`. PLAY, enabled editor lifecycle callbacks, explicit
`SceneUpdateRequest` owners and periodic extension callbacks keep updates
active. Pending component starts and primary-scene transitions request a tick.
Render invalidation is separate from continuous simulation demand. The
`request_updates(scene)` Python method returns an owner with `close()`; its
destruction also releases the request, including after scene destruction.

Scene mutations and work queries remain on the scene owner thread. The single
scene work callback is owned by its SceneManager and may only notify the host;
it must not mutate scenes reentrantly. Detached scenes have that callback
removed. Cross-thread producers enqueue owner-thread operations, rather than
mutating scene state directly.

After genuine inactivity the first resumed update has zero simulation delta.
Sleeping wall time is not accumulated as fixed-update debt. Active simulation
continues to receive elapsed time between due updates. Profiler frame cadence
is reset after inactivity. `monotonic_time` is injectable for deterministic
scheduler tests and must share the deadline domain used by `wait_until`.
