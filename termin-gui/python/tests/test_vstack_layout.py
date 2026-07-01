"""VStack layout tests."""

import pytest

from tcgui.widgets.vstack import VStack
from tests.conftest import make_widget, assert_rect, VIEWPORT_W, VIEWPORT_H

W, H = 400.0, 600.0


def _make_vstack(*children, spacing=0, justify="start"):
    vs = VStack()
    vs.spacing = spacing
    vs.justify = justify
    for c in children:
        vs.add_child(c)
    vs.layout(0, 0, W, H, VIEWPORT_W, VIEWPORT_H)
    return vs


def _assert_vstack(children, expected_rects, spacing=0, justify="start"):
    _make_vstack(*children, spacing=spacing, justify=justify)
    for child, rect in zip(children, expected_rects, strict=True):
        assert_rect(child, *rect)


# --- Basic ---

def test_empty():
    vs = VStack()
    vs.layout(0, 0, W, H, VIEWPORT_W, VIEWPORT_H)
    assert_rect(vs, 0, 0, W, H)


@pytest.mark.parametrize(
    ("children", "spacing", "expected_rects"),
    [
        ([make_widget(100, 50)], 0, [(0, 0, W, 50)]),
        ([make_widget(100, 30), make_widget(100, 50)], 0, [(0, 0, W, 30), (0, 30, W, 50)]),
        ([make_widget(100, 30), make_widget(100, 50)], 10, [(0, 0, W, 30), (0, 40, W, 50)]),
    ],
)
def test_fixed_children_layout(children, spacing, expected_rects):
    _assert_vstack(children, expected_rects, spacing=spacing)


# --- Stretch ---

def test_single_stretch():
    c = make_widget(stretch=True)
    _make_vstack(c)
    assert_rect(c, 0, 0, W, H)


@pytest.mark.parametrize(
    ("children", "spacing", "expected_rects"),
    [
        ([make_widget(100, 50), make_widget(stretch=True)], 0, [(0, 0, W, 50), (0, 50, W, 550)]),
        ([make_widget(stretch=True), make_widget(stretch=True)], 0, [(0, 0, W, 300), (0, 300, W, 300)]),
        ([make_widget(100, 50), make_widget(stretch=True)], 10, [(0, 0, W, 50), (0, 60, W, 540)]),
        ([make_widget(100, 400, stretch=True)], 0, [(0, 0, W, H)]),
        ([make_widget(100, 999, stretch=True)], 0, [(0, 0, W, H)]),
        ([make_widget(100, 50), make_widget(100, 999, stretch=True)], 10, [(0, 0, W, 50), (0, 60, W, 540)]),
    ],
)
def test_stretch_layout(children, spacing, expected_rects):
    _assert_vstack(children, expected_rects, spacing=spacing)


def test_compute_size_includes_stretch_preferred_height():
    fixed = make_widget(100, 50)
    stretch = make_widget(100, 180, stretch=True)
    vs = VStack()
    vs.spacing = 10
    vs.add_child(fixed)
    vs.add_child(stretch)

    assert vs.compute_size(VIEWPORT_W, VIEWPORT_H) == (100, 240)


# --- Invisible ---

def test_invisible_child_skipped():
    c1 = make_widget(100, 30)
    hidden = make_widget(100, 50)
    hidden.visible = False
    c2 = make_widget(100, 40)
    _make_vstack(c1, hidden, c2)
    assert_rect(c1, 0, 0, W, 30)
    assert_rect(c2, 0, 30, W, 40)


# --- Justify ---

@pytest.mark.parametrize(
    ("justify", "expected_rects"),
    [
        ("center", [(0, 250, W, 50), (0, 300, W, 50)]),
        ("end", [(0, 500, W, 50), (0, 550, W, 50)]),
    ],
)
def test_justify_layout(justify, expected_rects):
    children = [make_widget(100, 50), make_widget(100, 50)]
    _assert_vstack(children, expected_rects, justify=justify)


def test_justify_ignored_with_stretch():
    fixed = make_widget(100, 50)
    stretch = make_widget(stretch=True)
    _make_vstack(fixed, stretch, justify="center")
    # With stretch, justify is forced to "start"
    assert_rect(fixed, 0, 0, W, 50)
    assert_rect(stretch, 0, 50, W, 550)
