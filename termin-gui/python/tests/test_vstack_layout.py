"""VStack layout tests."""

from tcgui.widgets.vstack import VStack
from tcgui.widgets.units import px
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


# --- Basic ---

def test_empty():
    vs = VStack()
    vs.layout(0, 0, W, H, VIEWPORT_W, VIEWPORT_H)
    assert_rect(vs, 0, 0, W, H)


def test_single_child():
    c = make_widget(100, 50)
    _make_vstack(c)
    assert_rect(c, 0, 0, W, 50)


def test_two_children():
    c1 = make_widget(100, 30)
    c2 = make_widget(100, 50)
    _make_vstack(c1, c2)
    assert_rect(c1, 0, 0, W, 30)
    assert_rect(c2, 0, 30, W, 50)


def test_spacing():
    c1 = make_widget(100, 30)
    c2 = make_widget(100, 50)
    _make_vstack(c1, c2, spacing=10)
    assert_rect(c1, 0, 0, W, 30)
    assert_rect(c2, 0, 40, W, 50)


def test_children_get_full_width():
    c = make_widget(100, 50)
    _make_vstack(c)
    assert c.width == W


# --- Stretch ---

def test_single_stretch():
    c = make_widget(stretch=True)
    _make_vstack(c)
    assert_rect(c, 0, 0, W, H)


def test_stretch_with_fixed():
    fixed = make_widget(100, 50)
    stretch = make_widget(stretch=True)
    _make_vstack(fixed, stretch)
    assert_rect(fixed, 0, 0, W, 50)
    assert_rect(stretch, 0, 50, W, 550)


def test_two_stretch():
    s1 = make_widget(stretch=True)
    s2 = make_widget(stretch=True)
    _make_vstack(s1, s2)
    assert_rect(s1, 0, 0, W, 300)
    assert_rect(s2, 0, 300, W, 300)


def test_stretch_with_spacing():
    fixed = make_widget(100, 50)
    stretch = make_widget(stretch=True)
    # 3 children: fixed, stretch — spacing between pairs = 1 * 10
    # But we have 2 children, so spacing_total = 10
    _make_vstack(fixed, stretch, spacing=10)
    # remaining = 600 - 50 - 10 = 540
    assert_rect(fixed, 0, 0, W, 50)
    assert_rect(stretch, 0, 60, W, 540)


def test_stretch_ignores_preferred_height():
    c = make_widget(100, 999, stretch=True)
    _make_vstack(c)
    # stretch overrides preferred_height
    assert_rect(c, 0, 0, W, H)


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

def test_justify_center():
    c1 = make_widget(100, 50)
    c2 = make_widget(100, 50)
    _make_vstack(c1, c2, justify="center")
    # total = 100, offset = (600 - 100) / 2 = 250
    assert_rect(c1, 0, 250, W, 50)
    assert_rect(c2, 0, 300, W, 50)


def test_justify_end():
    c1 = make_widget(100, 50)
    c2 = make_widget(100, 50)
    _make_vstack(c1, c2, justify="end")
    # total = 100, offset = 600 - 100 = 500
    assert_rect(c1, 0, 500, W, 50)
    assert_rect(c2, 0, 550, W, 50)


def test_justify_ignored_with_stretch():
    fixed = make_widget(100, 50)
    stretch = make_widget(stretch=True)
    _make_vstack(fixed, stretch, justify="center")
    # With stretch, justify is forced to "start"
    assert_rect(fixed, 0, 0, W, 50)
    assert_rect(stretch, 0, 50, W, 550)
