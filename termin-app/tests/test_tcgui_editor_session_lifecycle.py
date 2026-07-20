from pathlib import Path

import pytest

from termin.editor_tcgui.editor_session import TcguiEditorSession
from termin.editor_tcgui.run_editor import _smoke_frame_limit


REPO_ROOT = Path(__file__).resolve().parents[2]


class _LoopConnection:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def detach(self) -> None:
        self.events.append("detach")


def test_tcgui_session_detaches_before_frontend_cleanup_exactly_once() -> None:
    events: list[str] = []
    session = TcguiEditorSession(
        _LoopConnection(events),
        lambda: events.append("cleanup"),
    )

    session.close()
    session.close()

    assert session.closed
    assert events == ["detach", "cleanup"]


def test_tcgui_frontend_uses_atomic_loop_session_and_external_teardown() -> None:
    source = (
        REPO_ROOT / "termin-app/termin/editor_tcgui/run_editor.py"
    ).read_text(encoding="utf-8")

    assert "EngineLoopClient(" in source
    assert "attach_loop_client(" in source
    assert "set_poll_events_callback(" not in source
    assert "set_should_continue_callback(" not in source
    assert "set_on_shutdown_callback(" not in source
    assert "finally:\n        session.close()" in source


def test_tcgui_window_releases_render_attachments_before_controller() -> None:
    source = (
        REPO_ROOT / "termin-app/termin/editor_tcgui/editor_window.py"
    ).read_text(encoding="utf-8")
    shutdown = source[source.index("    def shutdown(self) -> None:"):]

    detach_render = shutdown.index("self.detach_scene_from_render(")
    close_editor_attachment = shutdown.index("self._editor_attachment.close(")
    close_rendering_controller = shutdown.index("self._rendering_controller.close()")

    assert detach_render < close_rendering_controller
    assert close_editor_attachment < close_rendering_controller
    assert "self.scene_manager.set_on_after_render(None)" in shutdown
    assert "self.scene_manager.set_on_before_scene_close(None)" in shutdown


def test_tcgui_window_uses_its_private_engine_reference() -> None:
    source = (
        REPO_ROOT / "termin-app/termin/editor_tcgui/editor_window.py"
    ).read_text(encoding="utf-8")

    assert "self.engine" not in source
    assert "self._engine.rendering_manager.render_engine" in source


@pytest.mark.parametrize(
    ("value", "expected"),
    [("3", 3), ("0", 0), ("-2", 0), ("invalid", 0)],
)
def test_tcgui_smoke_frame_limit(monkeypatch, value: str, expected: int) -> None:
    monkeypatch.setenv("TERMIN_EDITOR_TCGUI_SMOKE_FRAMES", value)

    assert _smoke_frame_limit() == expected
