"""Engine-loop lifecycle for one native editor session."""

from __future__ import annotations

import os
from collections.abc import Callable

from tcbase import log

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
        quest_openxr_build_dialog,
        project_file_watcher,
        scene_structure_observer,
        spacemouse,
        framegraph_debugger,
        frame_profiler,
        profiler_panel,
        game_mode_controller,
        request_editor_render: Callable[[], None],
        window,
        frame_limit: int,
    ) -> None:
        self._terminal_interrupt = terminal_interrupt
        self._capture_profiler = capture_profiler
        self._window_manager = window_manager
        self._executor = executor
        self._host = host
        self._quest_openxr_build_dialog = quest_openxr_build_dialog
        self._project_file_watcher = project_file_watcher
        self._scene_structure_observer = scene_structure_observer
        self._spacemouse = spacemouse
        self._framegraph_debugger = framegraph_debugger
        self._frame_profiler = frame_profiler
        self._profiler_panel = profiler_panel
        self._game_mode_controller = game_mode_controller
        self._request_editor_render = request_editor_render
        self._window = window
        self._frame_limit = frame_limit
        self._frame_count = 0

    def poll_events(self) -> None:
        if self._terminal_interrupt.consume():
            log.info("[Editor] SIGINT received; requesting native editor shutdown")
            self._window.set_should_close(True)
            return
        with self._capture_profiler.section("Events"):
            keep_running, _routed = self._window_manager.poll_events()
        if not keep_running:
            return
        with self._capture_profiler.section("Queued Work"):
            if self._executor.process_pending() > 0:
                self._host.request_render_update()
            if self._quest_openxr_build_dialog.poll() > 0:
                self._host.request_render_update()
        with self._capture_profiler.section("Project Watch"):
            self._project_file_watcher.poll()
        with self._capture_profiler.section("Observers & Input"):
            self._scene_structure_observer.poll()
            self._spacemouse.poll()
        with self._capture_profiler.section("Debug Tools"):
            self._framegraph_debugger.update()
            self._frame_profiler.update()
            if self._profiler_panel.root.visible and self._profiler_panel.update():
                self._host.request_render_update()
        with self._capture_profiler.section("UI Schedule"):
            if _game_mode_requires_continuous_render(self._game_mode_controller):
                # Present the frame produced at the end of the previous loop and
                # keep the playing scene render scheduler active for the next one.
                self._request_editor_render()
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
    quest_openxr_build_dialog,
    project_file_watcher,
    scene_structure_observer,
    spacemouse,
    framegraph_debugger,
    frame_profiler,
    profiler_panel,
    game_mode_controller,
    request_editor_render: Callable[[], None],
    window,
) -> None:
    """Attach the native frontend loop and register its ordered teardown."""
    from termin.engine import EngineLoopClient

    event_loop_stage = session.begin_stage("event loop")
    terminal_interrupt = event_loop_stage.own(
        "terminal interrupt",
        TerminalInterruptController(),
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
            quest_openxr_build_dialog=quest_openxr_build_dialog,
            project_file_watcher=project_file_watcher,
            scene_structure_observer=scene_structure_observer,
            spacemouse=spacemouse,
            framegraph_debugger=framegraph_debugger,
            frame_profiler=frame_profiler,
            profiler_panel=profiler_panel,
            game_mode_controller=game_mode_controller,
            request_editor_render=request_editor_render,
            window=window,
            frame_limit=_smoke_frame_limit(),
        ),
    )
    loop_client = EngineLoopClient(
        poll_events=event_loop.poll_events,
        should_continue=event_loop.should_continue,
        on_shutdown=lambda: None,
    )
    loop_connection = event_loop_stage.own(
        "engine loop connection",
        engine.attach_loop_client(loop_client),
        cleanup=lambda: loop_connection.detach(),
    )
    terminal_interrupt.install()


__all__ = ["NativeEditorEventLoop", "attach_native_editor_event_loop"]
