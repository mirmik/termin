from pathlib import Path

import logging

import pytest

from termin.editor_native.editor_session import EditorSession


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_editor_session_closes_owned_stages_in_reverse_order_exactly_once() -> None:
    events: list[str] = []
    session = EditorSession()
    window = session.begin_stage("window")
    window.add_cleanup("SDL", lambda: events.append("SDL"))
    window.add_cleanup("window manager", lambda: events.append("window manager"))
    loop = session.begin_stage("event loop")
    loop.add_cleanup("terminal interrupt", lambda: events.append("terminal interrupt"))
    loop.add_cleanup("loop connection", lambda: events.append("loop connection"))

    session.close()
    session.close()

    assert session.closed
    assert events == ["loop connection", "terminal interrupt", "window manager", "SDL"]


@pytest.mark.parametrize("failure_stage", ["editor UI", "event loop"])
def test_editor_session_unwinds_completed_stages_after_injected_failure(
    failure_stage: str,
) -> None:
    events: list[str] = []

    def fail_at_boundary(name: str) -> None:
        if name == failure_stage:
            raise RuntimeError(f"injected failure at {name}")

    def compose(session: EditorSession) -> None:
        platform = session.begin_stage("platform")
        platform.add_cleanup("window", lambda: events.append("window"))
        editor_ui = session.begin_stage("editor UI")
        editor_ui.add_cleanup("shell", lambda: events.append("shell"))
        event_loop = session.begin_stage("event loop")
        event_loop.add_cleanup("loop connection", lambda: events.append("loop"))

    with pytest.raises(RuntimeError, match="injected failure"):
        EditorSession.build(compose, failure_injector=fail_at_boundary)

    expected = ["window"] if failure_stage == "editor UI" else ["shell", "window"]
    assert events == expected


def test_editor_session_logs_owner_and_continues_after_cleanup_failure(caplog) -> None:
    events: list[str] = []
    session = EditorSession()
    stage = session.begin_stage("editor UI")
    stage.add_cleanup("earlier object", lambda: events.append("earlier"))

    def fail_cleanup() -> None:
        raise RuntimeError("cleanup exploded")

    stage.add_cleanup("broken observer", fail_cleanup)
    stage.add_cleanup("later object", lambda: events.append("later"))

    with caplog.at_level(logging.ERROR):
        session.close()

    assert events == ["later", "earlier"]
    assert "stage='editor UI', object='broken observer'" in caplog.text


def test_native_editor_uses_host_owned_atomic_loop_session() -> None:
    frontend_source = (REPO_ROOT / "termin-app/termin/editor_native/run_editor.py").read_text(encoding="utf-8")
    host_source = (REPO_ROOT / "termin-app/cpp/app/main_minimal.cpp").read_text(encoding="utf-8")

    assert "EngineLoopClient(" in frontend_source
    assert "attach_loop_client(" in frontend_source
    assert "set_poll_events_callback(" not in frontend_source
    assert "set_should_continue_callback(" not in frontend_source
    assert "set_on_shutdown_callback(" not in frontend_source
    assert "engine.rendering_manager.shutdown()" not in frontend_source
    assert "PyObject* editor_session = initialize_python_editor(engine);" in host_source
    assert "close_python_editor(editor_session)" in host_source
