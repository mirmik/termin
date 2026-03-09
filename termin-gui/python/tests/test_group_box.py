"""GroupBox layout tests."""

from tcgui.widgets.group_box import GroupBox
from tcgui.widgets.units import px
from tests.conftest import make_widget, VIEWPORT_W, VIEWPORT_H


def test_collapsed_height():
    gb = GroupBox()
    gb.expanded = False
    gb.title_height = 28
    w, h = gb.compute_size(VIEWPORT_W, VIEWPORT_H)
    assert h == 28


def test_expanded_single_child():
    gb = GroupBox()
    gb.expanded = True
    gb.title_height = 28
    gb.content_padding = 8
    child = make_widget(100, 200)
    gb.add_child(child)
    w, h = gb.compute_size(VIEWPORT_W, VIEWPORT_H)
    # h = title_height + child_h + padding*2 = 28 + 200 + 16 = 244
    assert abs(h - 244) <= 0.5


def test_child_positioned_below_title():
    gb = GroupBox()
    gb.expanded = True
    gb.title_height = 28
    gb.content_padding = 8
    child = make_widget(100, 200)
    gb.add_child(child)

    gb.layout(10, 20, 300, 244, VIEWPORT_W, VIEWPORT_H)
    # child.y = gb.y + title_height + content_padding = 20 + 28 + 8 = 56
    assert abs(child.y - 56) <= 0.5
    # child.x = gb.x + content_padding = 10 + 8 = 18
    assert abs(child.x - 18) <= 0.5


def test_child_width_reduced_by_padding():
    gb = GroupBox()
    gb.expanded = True
    gb.content_padding = 8
    child = make_widget(100, 200)
    gb.add_child(child)

    gb.layout(0, 0, 300, 244, VIEWPORT_W, VIEWPORT_H)
    # child.width = 300 - 8*2 = 284
    assert abs(child.width - 284) <= 0.5


# --- Multiple children (BrushPanel-like) ---

def test_multiple_children_height():
    """GroupBox with spacing: title + children + gaps + padding*2."""
    gb = GroupBox()
    gb.expanded = True
    gb.title_height = 28
    gb.content_padding = 8
    gb.add_child(make_widget(0, 30))  # row
    gb.add_child(make_widget(0, 30))  # slider 1
    gb.add_child(make_widget(0, 30))  # slider 2
    w, h = gb.compute_size(VIEWPORT_W, VIEWPORT_H)
    # h = 28 + (30+30+30) + spacing*2 + 16
    expected = 28 + (30 + 30 + 30) + gb.spacing * 2 + 16
    assert abs(h - expected) <= 0.5


def test_multiple_children_positioned_vertically():
    """All children stacked vertically below title with spacing."""
    gb = GroupBox()
    gb.expanded = True
    gb.title_height = 28
    gb.content_padding = 8
    c1 = make_widget(0, 30)
    c2 = make_widget(0, 40)
    c3 = make_widget(0, 50)
    gb.add_child(c1)
    gb.add_child(c2)
    gb.add_child(c3)

    gb.layout(0, 0, 300, 200, VIEWPORT_W, VIEWPORT_H)
    # c1.y = 0 + 28 + 8 = 36
    assert abs(c1.y - 36) <= 0.5
    # c2.y = c1.y + 30 + spacing
    assert abs(c2.y - (36 + 30 + gb.spacing)) <= 0.5
    # c3.y = c2.y + 40 + spacing
    assert abs(c3.y - (36 + 30 + gb.spacing + 40 + gb.spacing)) <= 0.5


def test_invisible_child_skipped():
    gb = GroupBox()
    gb.expanded = True
    gb.title_height = 28
    gb.content_padding = 8
    c1 = make_widget(0, 30)
    hidden = make_widget(0, 30)
    hidden.visible = False
    c2 = make_widget(0, 30)
    gb.add_child(c1)
    gb.add_child(hidden)
    gb.add_child(c2)

    w, h = gb.compute_size(VIEWPORT_W, VIEWPORT_H)
    # h = 28 + (30+30) + spacing + 16 (hidden skipped)
    expected = 28 + (30 + 30) + gb.spacing + 16
    assert abs(h - expected) <= 0.5

    gb.layout(0, 0, 300, expected, VIEWPORT_W, VIEWPORT_H)
    # c2.y = 36 + 30 + spacing (no extra gap from hidden)
    assert abs(c2.y - (36 + 30 + gb.spacing)) <= 0.5
