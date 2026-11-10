"""Engine-loop lifecycle for one native editor session."""

from __future__ import annotations

import os
import time
from collections.abc import Callable

from termin.base import log

from termin.editor_core.terminal_interrupt import TerminalInterruptController


def _game_mode_requires_continuous_render(game_mode_controller) -> bool:
    return game_mode_controller is not None and game_mode_controller.model.is_game_mode


def _smoke_frame_limit() -> int:
    value = os.environ.get("TERMIN_EDITOR_NATIVE_SMOKE_FRAMES", "0")
    try:
        return max(int(value), 0)
    except ValueError:
        return 0


class NativeEditorEventLoop:
    """Coordinate one native editor iteration without owning its services."""

    def __init__(
        self,
        *,
        terminal_interrupt,
        capture_profiler,
        window_manager,
        executor,
        host,
        project_file_watcher,
        scene_structure_observer,
        spacemouse,
        framegraph_debugger,
        frame_profiler,
        profiler_panel,
        editor_log_capture,
        game_mode_controller,
        request_editor_render: Callable[[], None],
        window,
        frame_limit: int,
        editor_viewport,
        engine,
    ) -> None:
        self._terminal_interrupt = terminal_interrupt
        self._capture_profiler = capture_profiler
        self._window_manager = window_manager
        self._executor = executor
        self._host = host
        self._project_file_watcher = project_file_watcher
        self._scene_structure_observer = scene_structure_observer
        self._spacemouse = spacemouse
        self._framegraph_debugger = framegraph_debugger
        self._frame_profiler = frame_profiler
        self._profiler_panel = profiler_panel
        self._editor_log_capture = editor_log_capture
        self._game_mode_controller = game_mode_controller
        self._request_editor_render = request_editor_render
        self._window = window
        self._frame_limit = frame_limit
        self._frame_count = 0
        self._editor_viewport = editor_viewport
        self._engine = engine
        self._diagnostics_due = False
        self._next_debug_poll: float | None = None

    def connect_wakeups(self) -> None:
        wake = self._window_manager.wake
        self._executor.set_wakeup(wake)
        self._project_file_watcher.set_wakeup(wake)
        self._editor_log_capture.set_wakeup(wake)
        self._spacemouse.set_wakeup(wake)

    def close(self) -> None:
        self._spacemouse.set_wakeup(None)
        self._executor.set_wakeup(None)
        self._project_file_watcher.set_wakeup(None)
        self._editor_log_capture.set_wakeup(None)

    def plan_work(self, now: float):
        from termin.engine import EngineLoopPlan

        remote_debug = self._frame_profiler.needs_polling or self._framegraph_debugger.needs_polling
        if remote_debug and self._next_debug_poll is None:
            self._next_debug_poll = now
        elif not remote_debug:
            self._next_debug_poll = None
        deadlines = [deadline for deadline in (
            self._project_file_watcher.next_deadline, self._next_debug_poll,
        ) if deadline is not None]
        return EngineLoopPlan(
            immediate_work=bool(self._window_manager.has_pending_events
                                or self._executor.has_pending
                                or self._editor_log_capture.has_pending
                                or self._scene_structure_observer.pending
                                or self._diagnostics_due),
            frame_requested=bool(self._window_manager.render_ready or self._frame_limit > 0),
            continuous_update=bool(self._editor_viewport is not None
                                   and self._editor_viewport.needs_update),
            next_deadline=min(deadlines) if deadlines else None,
        )

    def poll_events(self) -> None:
        if self._terminal_interrupt.consume():
            log.info("[Editor] SIGINT received; requesting native editor shutdown")
            self._window.set_should_close(True)
            return
        with self._capture_profiler.section("Game Session"):
            if self._game_mode_controller is not None:
                self._game_mode_controller.model.refresh_primary_scene()
        with self._capture_profiler.section("Events"):
            keep_running, routed = self._window_manager.poll_events()
        if not keep_running:
            return
        with self._capture_profiler.section("Queued Work"):
            executed = self._executor.process_pending()
            if executed > 0:
                self._host.request_render_update()
        with self._capture_profiler.section("Project Watch"):
            self._project_file_watcher.poll()
        with self._capture_profiler.section("Observers & Input"):
            self._scene_structure_observer.poll()
            self._spacemouse.poll()
        now = time.monotonic()
        debug_deadline_due = self._next_debug_poll is not None and now >= self._next_debug_poll
        with self._capture_profiler.section("Debug Tools"):
            if self._diagnostics_due or routed or executed or debug_deadline_due:
                self._framegraph_debugger.update(frame_completed=self._diagnostics_due)
                self._diagnostics_due = False
                self._frame_profiler.update()
                if self._profiler_panel.root.visible and self._profiler_panel.update():
                    self._host.request_render_update()
            if debug_deadline_due:
                self._next_debug_poll = now + 0.1
        with self._capture_profiler.section("Editor Log"):
            if self._editor_log_capture.drain():
                self._host.request_render_update()

    def before_frame(self, dt: float) -> None:
        with self._capture_profiler.section("Editor Camera"):
            if self._editor_viewport is not None:
                self._editor_viewport.update(dt)
        with self._capture_profiler.section("UI Schedule"):
            if _game_mode_requires_continuous_render(self._game_mode_controller):
                self._request_editor_render()

    def after_frame(self) -> None:
        if self._engine.last_frame_rendered:
            self._host.request_render_update()
            # A profiler UI repaint must not produce its own perpetual stream
            # of presentation work. Refresh diagnostics only for scene work.
            self._diagnostics_due = True
        with self._capture_profiler.section("UI Compose"):
            self._window_manager.render_requested()
        self._frame_count += 1
        if self._frame_limit > 0 and self._frame_count >= self._frame_limit:
            self._window.set_should_close(True)

    def should_continue(self) -> bool:
        return not self._window.should_close()


def attach_native_editor_event_loop(
    session,
    engine,
    *,
    capture_profiler,
    window_manager,
    executor,
    host,
    project_file_watcher,
    scene_structure_observer,
    spacemouse,
    framegraph_debugger,
    frame_profiler,
    profiler_panel,
    editor_log_capture,
    game_mode_controller,
    request_editor_render: Callable[[], None],
    window,
    editor_viewport,
    frame_limit: int | None = None,
) -> None:
    """Attach the native frontend loop and register its ordered teardown."""
    from termin.engine import EngineLoopClient

    event_loop_stage = session.begin_stage("event loop")
    terminal_interrupt = event_loop_stage.own(
        "terminal interrupt",
        TerminalInterruptController(window_manager.wake),
        cleanup=lambda: terminal_interrupt.close(),
    )
    event_loop = event_loop_stage.own(
        "native editor event loop",
        NativeEditorEventLoop(
            terminal_interrupt=terminal_interrupt,
            capture_profiler=capture_profiler,
            window_manager=window_manager,
            executor=executor,
            host=host,
            project_file_watcher=project_file_watcher,
            scene_structure_observer=scene_structure_observer,
            spacemouse=spacemouse,
            framegraph_debugger=framegraph_debugger,
            frame_profiler=frame_profiler,
            profiler_panel=profiler_panel,
            editor_log_capture=editor_log_capture,
            game_mode_controller=game_mode_controller,
            request_editor_render=request_editor_render,
            window=window,
            editor_viewport=editor_viewport,
            frame_limit=_smoke_frame_limit() if frame_limit is None else frame_limit,
            engine=engine,
        ),
        cleanup=lambda: event_loop.close(),
    )
    event_loop.connect_wakeups()
    loop_client = EngineLoopClient(
        poll_events=event_loop.poll_events,
        should_continue=event_loop.should_continue,
        on_shutdown=lambda: None,
        plan_work=event_loop.plan_work,
        wait_until=window_manager.wait_until,
        wake=window_manager.wake,
        before_frame=event_loop.before_frame,
        after_frame=event_loop.after_frame,
        monotonic_time=time.monotonic,
    )
    loop_connection = event_loop_stage.own(
        "engine loop connection",
        engine.attach_loop_client(loop_client),
        cleanup=lambda: loop_connection.detach(),
    )
    terminal_interrupt.install()


__all__ = ["NativeEditorEventLoop", "attach_native_editor_event_loop"]
