"""HStack layout tests."""

import pytest

from tcgui.widgets.hstack import HStack
from tests.conftest import make_widget, assert_rect, VIEWPORT_W, VIEWPORT_H

W, H = 1280.0, 600.0


def _make_hstack(*children, spacing=0, justify="start"):
    hs = HStack()
    hs.spacing = spacing
    hs.justify = justify
    for c in children:
        hs.add_child(c)
    hs.layout(0, 0, W, H, VIEWPORT_W, VIEWPORT_H)
    return hs


def _assert_hstack(children, expected_rects, spacing=0, justify="start"):
    _make_hstack(*children, spacing=spacing, justify=justify)
    for child, rect in zip(children, expected_rects):
        assert_rect(child, *rect)


# --- Basic ---

def test_empty():
    hs = HStack()
    hs.layout(0, 0, W, H, VIEWPORT_W, VIEWPORT_H)
    assert_rect(hs, 0, 0, W, H)


@pytest.mark.parametrize(
    ("children", "spacing", "expected_rects"),
    [
        ([make_widget(100, 50)], 0, [(0, 0, 100, H)]),
        ([make_widget(100, 50), make_widget(200, 50)], 0, [(0, 0, 100, H), (100, 0, 200, H)]),
        ([make_widget(100, 50), make_widget(200, 50)], 10, [(0, 0, 100, H), (110, 0, 200, H)]),
    ],
)
def test_fixed_children_layout(children, spacing, expected_rects):
    _assert_hstack(children, expected_rects, spacing=spacing)


# --- Stretch ---

def test_single_stretch():
    c = make_widget(stretch=True)
    _make_hstack(c)
    assert_rect(c, 0, 0, W, H)


@pytest.mark.parametrize(
    ("children", "spacing", "expected_rects"),
    [
        ([make_widget(200, 50), make_widget(stretch=True)], 0, [(0, 0, 200, H), (200, 0, 1080, H)]),
        ([make_widget(stretch=True), make_widget(stretch=True)], 0, [(0, 0, 640, H), (640, 0, 640, H)]),
        ([make_widget(200, 50), make_widget(stretch=True)], 10, [(0, 0, 200, H), (210, 0, 1070, H)]),
        ([make_widget(999, 50, stretch=True)], 0, [(0, 0, W, H)]),
        ([make_widget(2000, 50, stretch=True)], 0, [(0, 0, W, H)]),
        ([make_widget(200, 50), make_widget(2000, 50, stretch=True)], 10, [(0, 0, 200, H), (210, 0, 1070, H)]),
    ],
)
def test_stretch_layout(children, spacing, expected_rects):
    _assert_hstack(children, expected_rects, spacing=spacing)


def test_compute_size_includes_stretch_preferred_width():
    fixed = make_widget(200, 50)
    stretch = make_widget(300, 50, stretch=True)
    hs = HStack()
    hs.spacing = 10
    hs.add_child(fixed)
    hs.add_child(stretch)

    assert hs.compute_size(VIEWPORT_W, VIEWPORT_H) == (510, 50)


# --- Invisible ---

def test_invisible_child_skipped():
    c1 = make_widget(100, 50)
    hidden = make_widget(200, 50)
    hidden.visible = False
    c2 = make_widget(150, 50)
    _make_hstack(c1, hidden, c2)
    assert_rect(c1, 0, 0, 100, H)
    assert_rect(c2, 100, 0, 150, H)


# --- Justify ---

@pytest.mark.parametrize(
    ("justify", "expected_rects"),
    [
        ("center", [(540, 0, 100, H), (640, 0, 100, H)]),
        ("end", [(1080, 0, 100, H), (1180, 0, 100, H)]),
    ],
)
def test_justify_layout(justify, expected_rects):
    children = [make_widget(100, 50), make_widget(100, 50)]
    _assert_hstack(children, expected_rects, justify=justify)


def test_justify_ignored_with_stretch():
    fixed = make_widget(200, 50)
    stretch = make_widget(stretch=True)
    _make_hstack(fixed, stretch, justify="center")
    assert_rect(fixed, 0, 0, 200, H)
    assert_rect(stretch, 200, 0, 1080, H)
