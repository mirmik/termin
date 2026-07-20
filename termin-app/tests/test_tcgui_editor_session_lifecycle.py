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


def test_tcgui_session_has_explicit_three_phase_shutdown() -> None:
    events: list[str] = []
    session = TcguiEditorSession(
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


def test_tcgui_session_rejects_backend_close_before_engine_phase() -> None:
    session = TcguiEditorSession(_LoopConnection([]), lambda: None, lambda: None)

    with pytest.raises(RuntimeError, match="prepare_engine_shutdown"):
        session.close()


def test_tcgui_frontend_uses_atomic_loop_session_and_external_teardown() -> None:
    source = (
        REPO_ROOT / "termin-app/termin/editor_tcgui/run_editor.py"
    ).read_text(encoding="utf-8")

    assert "EngineLoopClient(" in source
    assert "attach_loop_client(" in source
    assert "set_poll_events_callback(" not in source
    assert "set_should_continue_callback(" not in source
    assert "set_on_shutdown_callback(" not in source
    assert "engine.shutdown()" not in source[:source.index("def run_editor_tcgui(")]
    wrapper = source[source.index("def run_editor_tcgui("):]
    prepare = wrapper.index("session.prepare_engine_shutdown()")
    shutdown_engine = wrapper.index("engine.shutdown()", prepare)
    close = wrapper.index("session.close()", shutdown_engine)
    assert prepare < shutdown_engine < close


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


def test_tcgui_editor_input_manager_receives_full_display_handle() -> None:
    source = (
        REPO_ROOT / "termin-app/termin/editor_tcgui/editor_window.py"
    ).read_text(encoding="utf-8")
    setup = source[
        source.index("    def _setup_editor_viewport_input_managers("):
        source.index("    def _attach_editor_input_router(")
    ]

    assert "display_index, display_generation = display.handle" in setup
    assert "display_index,\n                display_generation," in setup


@pytest.mark.parametrize(
    ("value", "expected"),
    [("3", 3), ("0", 0), ("-2", 0), ("invalid", 0)],
)
def test_tcgui_smoke_frame_limit(monkeypatch, value: str, expected: int) -> None:
    monkeypatch.setenv("TERMIN_EDITOR_TCGUI_SMOKE_FRAMES", value)

    assert _smoke_frame_limit() == expected
