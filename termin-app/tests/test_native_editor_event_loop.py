from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from termin.editor_native import event_loop as event_loop_module
from termin.editor_native.editor_session import EditorSession
from termin.editor_native.event_loop import (
    NativeEditorEventLoop,
    _smoke_frame_limit,
    attach_native_editor_event_loop,
)


class _CaptureProfiler:
    def section(self, _name: str):
        return nullcontext()


def _build_event_loop(*, frame_limit: int = 0, game_mode: bool = False):
    terminal_interrupt = Mock()
    terminal_interrupt.consume.return_value = False
    window_manager = Mock()
    window_manager.poll_events.return_value = (True, 0)
    executor = Mock()
    executor.process_pending.return_value = 0
    host = Mock()
    quest_openxr_build_dialog = Mock()
    quest_openxr_build_dialog.poll.return_value = 0
    project_file_watcher = Mock()
    scene_structure_observer = Mock()
    spacemouse = Mock()
    framegraph_debugger = Mock()
    frame_profiler = Mock()
    profiler_panel = Mock()
    profiler_panel.root = SimpleNamespace(visible=False)
    game_mode_controller = SimpleNamespace(
        model=SimpleNamespace(is_game_mode=game_mode)
    )
    request_editor_render = Mock()
    window = Mock()
    window.should_close.return_value = False
    event_loop = NativeEditorEventLoop(
        terminal_interrupt=terminal_interrupt,
        capture_profiler=_CaptureProfiler(),
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
        frame_limit=frame_limit,
    )
    return event_loop, SimpleNamespace(
        terminal_interrupt=terminal_interrupt,
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
    )


def test_native_editor_event_loop_polls_services_and_honors_frame_limit() -> None:
    event_loop, services = _build_event_loop(frame_limit=1, game_mode=True)

    event_loop.poll_events()

    services.project_file_watcher.poll.assert_called_once_with()
    services.scene_structure_observer.poll.assert_called_once_with()
    services.spacemouse.poll.assert_called_once_with()
    services.framegraph_debugger.update.assert_called_once_with()
    services.frame_profiler.update.assert_called_once_with()
    services.request_editor_render.assert_called_once_with()
    services.window_manager.render_requested.assert_called_once_with()
    services.window.set_should_close.assert_called_once_with(True)


def test_native_editor_event_loop_interrupt_requests_shutdown_before_polling() -> None:
    event_loop, services = _build_event_loop()
    services.terminal_interrupt.consume.return_value = True

    event_loop.poll_events()

    services.window.set_should_close.assert_called_once_with(True)
    services.window_manager.poll_events.assert_not_called()


def test_native_editor_event_loop_should_continue_tracks_window() -> None:
    event_loop, services = _build_event_loop()
    assert event_loop.should_continue()

    services.window.should_close.return_value = True
    assert not event_loop.should_continue()


def test_attach_native_editor_event_loop_owns_reverse_order_teardown(
    monkeypatch,
) -> None:
    import termin.engine as engine_module

    events: list[str] = []
    terminal_interrupt = Mock()
    terminal_interrupt.close.side_effect = lambda: events.append("terminal close")
    monkeypatch.setattr(
        event_loop_module,
        "TerminalInterruptController",
        lambda: terminal_interrupt,
    )
    monkeypatch.setattr(
        engine_module,
        "EngineLoopClient",
        lambda **callbacks: SimpleNamespace(**callbacks),
    )
    connection = Mock()
    connection.detach.side_effect = lambda: events.append("detach")
    engine = Mock()
    engine.attach_loop_client.return_value = connection
    session = EditorSession()
    _event_loop, services = _build_event_loop()

    attach_native_editor_event_loop(
        session,
        engine,
        capture_profiler=_CaptureProfiler(),
        window_manager=services.window_manager,
        executor=services.executor,
        host=services.host,
        quest_openxr_build_dialog=services.quest_openxr_build_dialog,
        project_file_watcher=services.project_file_watcher,
        scene_structure_observer=services.scene_structure_observer,
        spacemouse=services.spacemouse,
        framegraph_debugger=services.framegraph_debugger,
        frame_profiler=services.frame_profiler,
        profiler_panel=services.profiler_panel,
        game_mode_controller=services.game_mode_controller,
        request_editor_render=services.request_editor_render,
        window=services.window,
    )

    terminal_interrupt.install.assert_called_once_with()
    engine.attach_loop_client.assert_called_once()
    loop_client = engine.attach_loop_client.call_args.args[0]
    assert callable(loop_client.poll_events)
    assert callable(loop_client.should_continue)
    session.prepare_engine_shutdown()
    assert events == ["detach", "terminal close"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [("12", 12), ("-3", 0), ("not-an-int", 0)],
)
def test_native_editor_smoke_frame_limit(monkeypatch, value: str, expected: int) -> None:
    monkeypatch.setenv("TERMIN_EDITOR_NATIVE_SMOKE_FRAMES", value)
    assert _smoke_frame_limit() == expected
