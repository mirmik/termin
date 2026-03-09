"""Panel layout tests."""

from tcgui.widgets.panel import Panel
from tcgui.widgets.units import px
from tests.conftest import make_widget, assert_rect, VIEWPORT_W, VIEWPORT_H

W, H = 400.0, 300.0


def _layout_panel(panel):
    panel.layout(0, 0, W, H, VIEWPORT_W, VIEWPORT_H)


# --- Padding ---

def test_no_padding():
    panel = Panel()
    panel.padding = 0
    child = make_widget(100, 50)
    panel.add_child(child)
    _layout_panel(panel)
    assert_rect(child, 0, 0, 100, 50)


def test_padding():
    panel = Panel()
    panel.padding = 10
    child = make_widget(100, 50)
    panel.add_child(child)
    _layout_panel(panel)
    assert_rect(child, 10, 10, 100, 50)


# --- compute_size ---

def test_compute_size_with_padding():
    panel = Panel()
    panel.padding = 10
    child = make_widget(100, 50)
    panel.add_child(child)
    w, h = panel.compute_size(VIEWPORT_W, VIEWPORT_H)
    assert abs(w - 120) <= 0.5
    assert abs(h - 70) <= 0.5


# --- Anchors ---

def test_anchor_center():
    panel = Panel()
    panel.padding = 0
    child = make_widget(100, 50)
    child.anchor = "center"
    panel.add_child(child)
    _layout_panel(panel)
    # centered: x = (400-100)/2 = 150, y = (300-50)/2 = 125
    assert_rect(child, 150, 125, 100, 50)


def test_anchor_bottom_right():
    panel = Panel()
    panel.padding = 0
    child = make_widget(100, 50)
    child.anchor = "bottom-right"
    panel.add_child(child)
    _layout_panel(panel)
    # x = 400-100 = 300, y = 300-50 = 250
    assert_rect(child, 300, 250, 100, 50)
