"""Splitter widget tests."""

import pytest

from tcgui.widgets.splitter import Splitter
from tcgui.widgets.events import MouseEvent
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


def _drag_splitter_width(
    *,
    side,
    down_x,
    move_x,
    min_size=None,
    max_size=None,
):
    target = _make_target(250)
    sp = Splitter(target=target, side=side)
    if min_size is not None:
        sp._min_size = min_size
    if max_size is not None:
        sp._max_size = max_size

    sp.on_mouse_down(MouseEvent(x=down_x, y=300, button=MouseButton.LEFT))
    assert sp._dragging is True
    sp.on_mouse_move(MouseEvent(x=move_x, y=300))

    return target.preferred_width.to_pixels(VIEWPORT_W)


@pytest.mark.parametrize(
    ("side", "down_x", "move_x", "expected_width"),
    [
        ("left", 250, 300, 200),
        ("right", 1000, 1050, 300),
    ],
)
def test_drag_side_resizes_target(side, down_x, move_x, expected_width):
    new_w = _drag_splitter_width(side=side, down_x=down_x, move_x=move_x)
    assert abs(new_w - expected_width) <= 0.5


# --- Constraints ---

@pytest.mark.parametrize(
    ("side", "down_x", "move_x", "min_size", "max_size", "expected_width"),
    [
        ("left", 250, 9999, 100, None, 100),
        ("right", 1000, 9999, None, 600, 600),
    ],
)
def test_drag_respects_width_constraints(
    side,
    down_x,
    move_x,
    min_size,
    max_size,
    expected_width,
):
    new_w = _drag_splitter_width(
        side=side,
        down_x=down_x,
        move_x=move_x,
        min_size=min_size,
        max_size=max_size,
    )
    assert abs(new_w - expected_width) <= 0.5
