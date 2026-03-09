"""Splitter widget tests."""

from tcgui.widgets.splitter import Splitter
from tcgui.widgets.events import MouseEvent
from tcgui.widgets.units import px
from tcbase import MouseButton
from tests.conftest import make_widget, VIEWPORT_W, VIEWPORT_H


def _make_target(w=250):
    target = make_widget(w, 600)
    return target


# --- Basic ---

def test_compute_size():
    target = _make_target()
    sp = Splitter(target=target, side="left")
    w, h = sp.compute_size(VIEWPORT_W, VIEWPORT_H)
    assert w == 5
    assert h == 0


def test_initial_state():
    target = _make_target()
    sp = Splitter(target=target, side="left")
    assert sp._dragging is False
    assert sp._hovered is False


# --- Drag left side ---

def test_drag_left_side():
    target = _make_target(250)
    sp = Splitter(target=target, side="left")

    ev_down = MouseEvent(x=250, y=300, button=MouseButton.LEFT)
    sp.on_mouse_down(ev_down)
    assert sp._dragging is True

    ev_move = MouseEvent(x=300, y=300)
    sp.on_mouse_move(ev_move)

    new_w = target.preferred_width.to_pixels(VIEWPORT_W)
    assert abs(new_w - 200) <= 0.5


# --- Drag right side ---

def test_drag_right_side():
    target = _make_target(250)
    sp = Splitter(target=target, side="right")

    ev_down = MouseEvent(x=1000, y=300, button=MouseButton.LEFT)
    sp.on_mouse_down(ev_down)

    ev_move = MouseEvent(x=1050, y=300)
    sp.on_mouse_move(ev_move)

    new_w = target.preferred_width.to_pixels(VIEWPORT_W)
    assert abs(new_w - 300) <= 0.5


# --- Constraints ---

def test_min_width_constraint():
    target = _make_target(250)
    sp = Splitter(target=target, side="left")
    sp._min_size = 100

    ev_down = MouseEvent(x=250, y=300, button=MouseButton.LEFT)
    sp.on_mouse_down(ev_down)

    ev_move = MouseEvent(x=9999, y=300)
    sp.on_mouse_move(ev_move)

    new_w = target.preferred_width.to_pixels(VIEWPORT_W)
    assert abs(new_w - 100) <= 0.5


def test_max_width_constraint():
    target = _make_target(250)
    sp = Splitter(target=target, side="right")
    sp._max_size = 600

    ev_down = MouseEvent(x=1000, y=300, button=MouseButton.LEFT)
    sp.on_mouse_down(ev_down)

    ev_move = MouseEvent(x=9999, y=300)
    sp.on_mouse_move(ev_move)

    new_w = target.preferred_width.to_pixels(VIEWPORT_W)
    assert abs(new_w - 600) <= 0.5
