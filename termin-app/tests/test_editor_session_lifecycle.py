from pathlib import Path

import pytest

from termin.editor_native.editor_session import EditorSession


REPO_ROOT = Path(__file__).resolve().parents[2]


class _LoopConnection:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def detach(self) -> None:
        self.events.append("detach")


def test_editor_session_has_explicit_three_phase_shutdown() -> None:
    events: list[str] = []
    session = EditorSession(
        _LoopConnection(events),
        lambda: events.append("prepare"),
        lambda: events.append("backend"),
    )

    session.prepare_engine_shutdown()
    session.prepare_engine_shutdown()
    session.close()
    session.close()

    assert session.prepared
    assert session.closed
    assert events == ["detach", "prepare", "backend"]


def test_editor_session_rejects_backend_close_before_engine_phase() -> None:
    session = EditorSession(_LoopConnection([]), lambda: None, lambda: None)

    with pytest.raises(RuntimeError, match="prepare_engine_shutdown"):
        session.close()


def test_native_editor_uses_host_owned_atomic_loop_session() -> None:
    frontend_source = (
        REPO_ROOT / "termin-app/termin/editor_native/run_editor.py"
    ).read_text(encoding="utf-8")
    host_source = (
        REPO_ROOT / "termin-app/cpp/app/main_minimal.cpp"
    ).read_text(encoding="utf-8")

    assert "EngineLoopClient(" in frontend_source
    assert "attach_loop_client(" in frontend_source
    assert "set_poll_events_callback(" not in frontend_source
    assert "set_should_continue_callback(" not in frontend_source
    assert "set_on_shutdown_callback(" not in frontend_source
    assert "engine.rendering_manager.shutdown()" not in frontend_source
    assert "engine.shutdown()" not in frontend_source
    prepare = host_source.index(
        'call_python_editor_method(editor_session, "prepare_engine_shutdown")'
    )
    shutdown_engine = host_source.index("engine.shutdown()", prepare)
    close = host_source.index(
        'call_python_editor_method(editor_session, "close")', shutdown_engine
    )
    assert prepare < shutdown_engine < close
    assert "PyObject* editor_session = initialize_python_editor(engine);" in host_source
    assert "call_python_editor_method(editor_session" in host_source
