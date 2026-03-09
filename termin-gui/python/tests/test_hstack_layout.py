"""HStack layout tests."""

from tcgui.widgets.hstack import HStack
from tcgui.widgets.units import px
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


# --- Basic ---

def test_empty():
    hs = HStack()
    hs.layout(0, 0, W, H, VIEWPORT_W, VIEWPORT_H)
    assert_rect(hs, 0, 0, W, H)


def test_single_child():
    c = make_widget(100, 50)
    _make_hstack(c)
    assert_rect(c, 0, 0, 100, H)


def test_two_children():
    c1 = make_widget(100, 50)
    c2 = make_widget(200, 50)
    _make_hstack(c1, c2)
    assert_rect(c1, 0, 0, 100, H)
    assert_rect(c2, 100, 0, 200, H)


def test_spacing():
    c1 = make_widget(100, 50)
    c2 = make_widget(200, 50)
    _make_hstack(c1, c2, spacing=10)
    assert_rect(c1, 0, 0, 100, H)
    assert_rect(c2, 110, 0, 200, H)


def test_children_get_full_height():
    c = make_widget(100, 50)
    _make_hstack(c)
    assert c.height == H


# --- Stretch ---

def test_single_stretch():
    c = make_widget(stretch=True)
    _make_hstack(c)
    assert_rect(c, 0, 0, W, H)


def test_stretch_with_fixed():
    fixed = make_widget(200, 50)
    stretch = make_widget(stretch=True)
    _make_hstack(fixed, stretch)
    assert_rect(fixed, 0, 0, 200, H)
    assert_rect(stretch, 200, 0, 1080, H)


def test_two_stretch():
    s1 = make_widget(stretch=True)
    s2 = make_widget(stretch=True)
    _make_hstack(s1, s2)
    assert_rect(s1, 0, 0, 640, H)
    assert_rect(s2, 640, 0, 640, H)


def test_stretch_with_spacing():
    fixed = make_widget(200, 50)
    stretch = make_widget(stretch=True)
    _make_hstack(fixed, stretch, spacing=10)
    # remaining = 1280 - 200 - 10 = 1070
    assert_rect(fixed, 0, 0, 200, H)
    assert_rect(stretch, 210, 0, 1070, H)


def test_stretch_ignores_preferred_width():
    c = make_widget(999, 50, stretch=True)
    _make_hstack(c)
    assert_rect(c, 0, 0, W, H)


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

def test_justify_center():
    c1 = make_widget(100, 50)
    c2 = make_widget(100, 50)
    _make_hstack(c1, c2, justify="center")
    # total = 200, offset = (1280 - 200) / 2 = 540
    assert_rect(c1, 540, 0, 100, H)
    assert_rect(c2, 640, 0, 100, H)


def test_justify_end():
    c1 = make_widget(100, 50)
    c2 = make_widget(100, 50)
    _make_hstack(c1, c2, justify="end")
    # total = 200, offset = 1280 - 200 = 1080
    assert_rect(c1, 1080, 0, 100, H)
    assert_rect(c2, 1180, 0, 100, H)


def test_justify_ignored_with_stretch():
    fixed = make_widget(200, 50)
    stretch = make_widget(stretch=True)
    _make_hstack(fixed, stretch, justify="center")
    assert_rect(fixed, 0, 0, 200, H)
    assert_rect(stretch, 200, 0, 1080, H)
