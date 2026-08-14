import pytest


def test_player_backend_window_receives_requested_presentation_mode():
    from termin.display.window import PresentationMode
    from termin.player.runtime import _create_player_backend_window

    calls = []

    class GraphicsSession:
        def create_window(self, title, width, height, *, presentation_mode):
            calls.append((title, width, height, presentation_mode))
            return object()

    _create_player_backend_window(
        GraphicsSession(),
        title="Game",
        width=1280,
        height=720,
        vsync=False,
    )

    assert calls == [("Game", 1280, 720, PresentationMode.IMMEDIATE)]


def test_player_backend_window_reports_unsupported_requested_mode():
    from termin.player.runtime import _create_player_backend_window

    class GraphicsSession:
        def create_window(self, _title, _width, _height, *, presentation_mode):
            raise RuntimeError(f"unsupported {presentation_mode}")

    with pytest.raises(
        RuntimeError,
        match="requested presentation mode 'immediate'",
    ):
        _create_player_backend_window(
            GraphicsSession(),
            title="Game",
            width=1280,
            height=720,
            vsync=False,
        )
