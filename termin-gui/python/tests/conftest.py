"""Helpers for layout tests."""

from tcgui.widgets.widget import Widget
from tcgui.widgets.units import px, pct

VIEWPORT_W = 1280.0
VIEWPORT_H = 800.0


def make_widget(w=0, h=0, stretch=False):
    """Create a Widget with given preferred size."""
    widget = Widget()
    if w > 0:
        widget.preferred_width = px(w)
    if h > 0:
        widget.preferred_height = px(h)
    widget.stretch = stretch
    return widget


def assert_rect(widget, x, y, w, h, tol=0.5):
    """Assert widget position and size within tolerance."""
    assert abs(widget.x - x) <= tol, f"x: expected {x}, got {widget.x}"
    assert abs(widget.y - y) <= tol, f"y: expected {y}, got {widget.y}"
    assert abs(widget.width - w) <= tol, f"width: expected {w}, got {widget.width}"
    assert abs(widget.height - h) <= tol, f"height: expected {h}, got {widget.height}"
