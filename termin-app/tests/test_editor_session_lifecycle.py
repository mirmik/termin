from pathlib import Path

from termin.editor_native.editor_session import EditorSession


REPO_ROOT = Path(__file__).resolve().parents[2]


class _LoopConnection:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def detach(self) -> None:
        self.events.append("detach")


def test_editor_session_detaches_before_frontend_cleanup_exactly_once() -> None:
    events: list[str] = []
    session = EditorSession(
        _LoopConnection(events),
        lambda: events.append("cleanup"),
    )

    session.close()
    session.close()

    assert session.closed
    assert events == ["detach", "cleanup"]


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
    assert "PyObject* editor_session = initialize_python_editor(engine);" in host_source
    assert "close_python_editor(editor_session)" in host_source
