"""ScrollArea layout tests."""

from tcgui.widgets.scroll_area import ScrollArea
from tcgui.widgets.units import px
from tests.conftest import make_widget, assert_rect, VIEWPORT_W, VIEWPORT_H


def _make_scroll_area(sa_w, sa_h, content_w, content_h, scroll_y=0.0):
    sa = ScrollArea()
    sa.preferred_width = px(sa_w)
    sa.preferred_height = px(sa_h)
    sa.scroll_y = scroll_y

    content = make_widget(content_w, content_h)
    sa.add_child(content)

    sa.layout(0, 0, sa_w, sa_h, VIEWPORT_W, VIEWPORT_H)
    return sa, content


# --- compute_size ---

def test_compute_size_with_preferred():
    sa = ScrollArea()
    sa.preferred_width = px(300)
    sa.preferred_height = px(200)
    w, h = sa.compute_size(VIEWPORT_W, VIEWPORT_H)
    assert w == 300
    assert h == 200


def test_compute_size_defaults():
    sa = ScrollArea()
    w, h = sa.compute_size(VIEWPORT_W, VIEWPORT_H)
    assert w == 200
    assert h == 200


# --- Layout ---

def test_content_smaller_than_viewport():
    sa, content = _make_scroll_area(400, 300, 100, 100)
    assert sa._max_scroll_y == 0
    assert sa.scroll_y == 0


def test_content_larger_vertical():
    sa, content = _make_scroll_area(400, 300, 400, 1000)
    assert sa._max_scroll_y == 700


def test_scroll_clamp():
    sa, content = _make_scroll_area(400, 300, 400, 1000, scroll_y=9999)
    assert sa.scroll_y == 700


def test_content_position_with_scroll():
    sa, content = _make_scroll_area(400, 300, 400, 1000, scroll_y=100)
    # content.y = sa.y - scroll_y = 0 - 100 = -100
    assert abs(content.y - (-100)) <= 0.5


def test_content_gets_max_dimension():
    sa, content = _make_scroll_area(400, 300, 200, 1000)
    # content width = max(200, 400) = 400
    assert abs(content.width - 400) <= 0.5
    # content height = max(1000, 300) = 1000
    assert abs(content.height - 1000) <= 0.5


def test_scroll_zero_when_content_fits():
    sa, content = _make_scroll_area(400, 300, 100, 100, scroll_y=50)
    # max_scroll_y = 0, so scroll_y clamped to 0
    assert sa.scroll_y == 0
