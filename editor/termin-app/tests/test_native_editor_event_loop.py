from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import termin.editor_native.event_loop as event_loop_module
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
    window_manager.has_pending_events = False
    window_manager.render_ready = False
    executor = Mock()
    executor.process_pending.return_value = 0
    executor.has_pending = False
    host = Mock()
    project_file_watcher = Mock()
    project_file_watcher.next_deadline = None
    scene_structure_observer = Mock()
    scene_structure_observer.pending = False
    spacemouse = Mock()
    framegraph_debugger = Mock()
    framegraph_debugger.needs_polling = False
    frame_profiler = Mock()
    frame_profiler.needs_polling = False
    profiler_panel = Mock()
    profiler_panel.root = SimpleNamespace(visible=False)
    editor_log_capture = Mock()
    editor_log_capture.drain.return_value = False
    editor_log_capture.has_pending = False
    game_mode_controller = SimpleNamespace(
        model=SimpleNamespace(
            is_game_mode=game_mode,
            refresh_primary_scene=Mock(),
        )
    )
    editor_viewport = Mock()
    editor_viewport.needs_update = False
    engine = SimpleNamespace(last_frame_rendered=False)
    request_editor_render = Mock()
    window = Mock()
    window.should_close.return_value = False
    event_loop = NativeEditorEventLoop(
        terminal_interrupt=terminal_interrupt,
        capture_profiler=_CaptureProfiler(),
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
        editor_viewport=editor_viewport,
        window=window,
        frame_limit=frame_limit,
        engine=engine,
    )
    return event_loop, SimpleNamespace(
        terminal_interrupt=terminal_interrupt,
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
        editor_viewport=editor_viewport,
        window=window,
        engine=engine,
    )


def test_native_editor_event_loop_polls_services_and_honors_frame_limit() -> None:
    event_loop, services = _build_event_loop(frame_limit=1, game_mode=True)

    event_loop.poll_events()
    services.window_manager.render_requested.assert_not_called()
    services.editor_viewport.update.assert_not_called()
    services.window.set_should_close.assert_not_called()
    event_loop.before_frame(0.125)
    event_loop.after_frame()

    services.project_file_watcher.poll.assert_called_once_with()
    services.game_mode_controller.model.refresh_primary_scene.assert_called_once_with()
    services.scene_structure_observer.poll.assert_called_once_with()
    services.spacemouse.poll.assert_called_once_with()
    services.framegraph_debugger.update.assert_not_called()
    services.frame_profiler.update.assert_not_called()
    services.editor_log_capture.drain.assert_called_once_with()
    services.request_editor_render.assert_called_once_with()
    services.window_manager.render_requested.assert_called_once_with()
    services.window.set_should_close.assert_called_once_with(True)


def test_native_editor_event_loop_interrupt_requests_shutdown_before_polling() -> None:
    event_loop, services = _build_event_loop()
    services.terminal_interrupt.consume.return_value = True

    event_loop.poll_events()

    services.window.set_should_close.assert_called_once_with(True)
    services.window_manager.poll_events.assert_not_called()
    services.game_mode_controller.model.refresh_primary_scene.assert_not_called()


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
        lambda wake: terminal_interrupt,
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
        project_file_watcher=services.project_file_watcher,
        scene_structure_observer=services.scene_structure_observer,
        spacemouse=services.spacemouse,
        framegraph_debugger=services.framegraph_debugger,
        frame_profiler=services.frame_profiler,
        profiler_panel=services.profiler_panel,
        editor_log_capture=services.editor_log_capture,
        game_mode_controller=services.game_mode_controller,
        request_editor_render=services.request_editor_render,
        editor_viewport=services.editor_viewport,
        window=services.window,
    )

    terminal_interrupt.install.assert_called_once_with()
    engine.attach_loop_client.assert_called_once()
    loop_client = engine.attach_loop_client.call_args.args[0]
    assert callable(loop_client.poll_events)
    assert callable(loop_client.should_continue)
    assert callable(loop_client.plan_work)
    assert callable(loop_client.before_frame)
    assert callable(loop_client.after_frame)
    assert loop_client.wait_until == services.window_manager.wait_until
    assert loop_client.wake == services.window_manager.wake
    for service in (services.executor, services.project_file_watcher,
                    services.editor_log_capture, services.spacemouse):
        service.set_wakeup.assert_called_once_with(services.window_manager.wake)
    session.prepare_engine_shutdown()
    assert events == ["detach", "terminal close"]
    for service in (services.executor, services.project_file_watcher,
                    services.editor_log_capture, services.spacemouse):
        assert service.set_wakeup.call_args.args == (None,)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("12", 12), ("-3", 0), ("not-an-int", 0)],
)
def test_native_editor_smoke_frame_limit(monkeypatch, value: str, expected: int) -> None:
    monkeypatch.setenv("TERMIN_EDITOR_NATIVE_SMOKE_FRAMES", value)
    assert _smoke_frame_limit() == expected


def test_idle_camera_updates_after_input_before_composition(monkeypatch):
    monkeypatch.setattr(event_loop_module.time, "monotonic", lambda: 10.0)
    loop, services = _build_event_loop()
    order = []
    services.spacemouse.poll.side_effect = lambda: order.append("input")
    services.editor_viewport.update.side_effect = lambda dt: order.append(("camera", dt))
    services.window_manager.render_requested.side_effect = lambda: order.append("compose")
    loop.poll_events()
    loop.before_frame(.125)
    loop.after_frame()
    loop.poll_events()
    loop.before_frame(.125)
    loop.after_frame()
    assert order == ["input", ("camera", .125), "compose"] * 2
    services.request_editor_render.assert_not_called()


def test_idle_plan_has_no_work_or_periodic_frame_deadline() -> None:
    loop, services = _build_event_loop()
    for now in (1.0, 60.0, 3600.0):
        plan = loop.plan_work(now)
        assert not plan.immediate_work
        assert not plan.frame_requested
        assert not plan.continuous_update
        assert plan.next_deadline is None
    services.editor_viewport.needs_update = True
    assert loop.plan_work(3601.0).continuous_update
    services.editor_viewport.needs_update = False
    services.window_manager.render_ready = True
    plan = loop.plan_work(3602.0)
    assert plan.frame_requested
    assert not plan.continuous_update


def test_watcher_debounce_is_deadline_not_immediate_work() -> None:
    loop, services = _build_event_loop()
    services.project_file_watcher.has_pending = True
    services.project_file_watcher.next_deadline = 10.5
    plan = loop.plan_work(10.0)
    assert plan.next_deadline == 10.5
    assert not plan.immediate_work
    assert not plan.frame_requested
    services.project_file_watcher.next_deadline = 11.0
    assert loop.plan_work(10.2).next_deadline == 11.0


@pytest.mark.parametrize("source", ["executor", "editor_log_capture", "window_manager",
                                    "scene_structure_observer"])
def test_published_backlog_keeps_service_work_ready(source) -> None:
    loop, services = _build_event_loop()
    if source == "executor":
        services.executor.has_pending = True
    elif source == "editor_log_capture":
        services.editor_log_capture.has_pending = True
    elif source == "window_manager":
        services.window_manager.has_pending_events = True
    else:
        services.scene_structure_observer.pending = True
    plan = loop.plan_work(1.0)
    assert plan.immediate_work
    assert not plan.frame_requested
    assert not plan.continuous_update


def test_profiler_ui_frame_does_not_schedule_its_own_refresh() -> None:
    loop, services = _build_event_loop()
    services.profiler_panel.root.visible = True
    services.profiler_panel.update.return_value = True
    # A scene frame produces one diagnostic update and its requested UI repaint.
    services.engine.last_frame_rendered = True
    loop.after_frame()
    assert loop.plan_work(1.0).immediate_work
    loop.poll_events()
    services.framegraph_debugger.update.assert_called_once_with(frame_completed=True)
    services.frame_profiler.update.assert_called_once_with()
    services.profiler_panel.update.assert_called_once_with()
    services.engine.last_frame_rendered = False
    loop.after_frame()
    assert not loop.plan_work(1.1).immediate_work
    loop.poll_events()
    services.frame_profiler.update.assert_called_once_with()
    services.profiler_panel.update.assert_called_once_with()
    assert loop.plan_work(10.0).next_deadline is None


def test_remote_debug_refresh_has_deadline_and_stops_when_closed(monkeypatch) -> None:
    loop, services = _build_event_loop()
    now = [10.0]
    monkeypatch.setattr(event_loop_module.time, "monotonic", lambda: now[0])
    services.frame_profiler.needs_polling = True
    assert loop.plan_work(now[0]).next_deadline == 10.0
    loop.poll_events()
    assert loop.plan_work(now[0]).next_deadline == pytest.approx(10.1)
    services.framegraph_debugger.update.assert_called_once_with(frame_completed=False)
    services.frame_profiler.update.assert_called_once_with()
    now[0] = 10.05
    loop.poll_events()
    services.frame_profiler.update.assert_called_once_with()
    services.frame_profiler.needs_polling = False
    assert loop.plan_work(now[0]).next_deadline is None
