"""Viewport3D input forwarding tests."""

from __future__ import annotations

from tcbase import MouseButton
from tcgui.widgets.events import MouseEvent, MouseWheelEvent
from tcgui.widgets.viewport3d import Viewport3D


class _Surface:
    def framebuffer_size(self) -> tuple[int, int]:
        return (600, 400)

    def resize(self, _width: int, _height: int) -> bool:
        return True


class _Display:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def dispatch_pointer_move(self, x: float, y: float) -> None:
        self.calls.append(("move", x, y))

    def dispatch_pointer_button(
        self, x: float, y: float, button: int, action: int, mods: int, clicks: int
    ) -> None:
        self.calls.append(("button", x, y, button, action, mods, clicks))

    def dispatch_wheel(
        self, x: float, y: float, dx: float, dy: float, mods: int
    ) -> None:
        self.calls.append(("scroll", x, y, dx, dy, mods))


def _viewport_with_input(x: float, y: float) -> tuple[Viewport3D, _Display]:
    viewport = Viewport3D()
    display = _Display()
    viewport._display = display
    viewport._surface = _Surface()
    viewport.layout(x, y, 300.0, 200.0, 800.0, 600.0)
    return viewport, display


def test_mouse_down_syncs_position_before_button() -> None:
    viewport, display = _viewport_with_input(10.0, 20.0)

    handled = viewport.on_mouse_down(MouseEvent(42.0, 65.0, MouseButton.LEFT, 7))

    assert handled is True
    assert display.calls == [
        ("move", 64.0, 90.0),
        ("button", 64.0, 90.0, 0, 1, 7, 1),
    ]


def test_mouse_up_syncs_position_before_button() -> None:
    viewport, display = _viewport_with_input(5.0, 8.0)

    viewport.on_mouse_up(MouseEvent(25.0, 38.0, MouseButton.RIGHT, 3))

    assert display.calls == [
        ("move", 40.0, 60.0),
        ("button", 40.0, 60.0, 1, 0, 3, 1),
    ]


def test_mouse_wheel_syncs_position_before_scroll() -> None:
    viewport, display = _viewport_with_input(3.0, 4.0)

    handled = viewport.on_mouse_wheel(MouseWheelEvent(6.0, -2.0, 13.0, 24.0, 5))

    assert handled is True
    assert display.calls == [
        ("move", 20.0, 40.0),
        ("scroll", 20.0, 40.0, 6.0, -2.0, 5),
    ]
