"""Viewport3D input forwarding tests."""

from __future__ import annotations

import sys
import types

from tcbase import MouseButton
from tcgui.widgets.events import MouseEvent, MouseWheelEvent
from tcgui.widgets.viewport3d import Viewport3D


def _install_display_input_stub(monkeypatch) -> list[tuple]:
    calls: list[tuple] = []
    termin_module = types.ModuleType("termin")
    display_module = types.ModuleType("termin.display")

    def on_mouse_move(ptr: int, x: float, y: float) -> None:
        calls.append(("move", ptr, x, y))

    def on_mouse_button(ptr: int, button: int, action: int, mods: int) -> None:
        calls.append(("button", ptr, button, action, mods))

    def on_scroll(ptr: int, dx: float, dy: float, mods: int) -> None:
        calls.append(("scroll", ptr, dx, dy, mods))

    display_module._input_manager_on_mouse_move = on_mouse_move
    display_module._input_manager_on_mouse_button = on_mouse_button
    display_module._input_manager_on_scroll = on_scroll
    termin_module.display = display_module

    monkeypatch.setitem(sys.modules, "termin", termin_module)
    monkeypatch.setitem(sys.modules, "termin.display", display_module)
    return calls


def test_mouse_down_syncs_position_before_button(monkeypatch) -> None:
    calls = _install_display_input_stub(monkeypatch)
    viewport = Viewport3D()
    viewport._input_manager_ptr = 123
    viewport.layout(10.0, 20.0, 300.0, 200.0, 800.0, 600.0)

    handled = viewport.on_mouse_down(MouseEvent(42.0, 65.0, MouseButton.LEFT, 7))

    assert handled is True
    assert calls == [
        ("move", 123, 32.0, 45.0),
        ("button", 123, 0, 1, 7),
    ]


def test_mouse_up_syncs_position_before_button(monkeypatch) -> None:
    calls = _install_display_input_stub(monkeypatch)
    viewport = Viewport3D()
    viewport._input_manager_ptr = 456
    viewport.layout(5.0, 8.0, 300.0, 200.0, 800.0, 600.0)

    viewport.on_mouse_up(MouseEvent(25.0, 38.0, MouseButton.RIGHT, 3))

    assert calls == [
        ("move", 456, 20.0, 30.0),
        ("button", 456, 1, 0, 3),
    ]


def test_mouse_wheel_syncs_position_before_scroll(monkeypatch) -> None:
    calls = _install_display_input_stub(monkeypatch)
    viewport = Viewport3D()
    viewport._input_manager_ptr = 789
    viewport.layout(3.0, 4.0, 300.0, 200.0, 800.0, 600.0)

    handled = viewport.on_mouse_wheel(MouseWheelEvent(6.0, -2.0, 13.0, 24.0, 5))

    assert handled is True
    assert calls == [
        ("move", 789, 10.0, 20.0),
        ("scroll", 789, 6.0, -2.0, 5),
    ]
