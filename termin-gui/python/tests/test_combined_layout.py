"""Combined layout tests — nested containers, real-world scenarios."""

from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.scroll_area import ScrollArea
from tcgui.widgets.splitter import Splitter
from tcgui.widgets.events import MouseEvent
from tcgui.widgets.units import px
from tcbase import MouseButton
from tests.conftest import make_widget, assert_rect, VIEWPORT_W, VIEWPORT_H


# --- Nested containers ---

def test_hstack_with_vstack_children():
    """HStack[VStack(w=100), VStack(w=200)]"""
    hs = HStack()
    vs1 = VStack()
    vs1.preferred_width = px(100)
    vs2 = VStack()
    vs2.preferred_width = px(200)
    hs.add_child(vs1)
    hs.add_child(vs2)

    hs.layout(0, 0, 500, 400, VIEWPORT_W, VIEWPORT_H)
    assert_rect(vs1, 0, 0, 100, 400)
    assert_rect(vs2, 100, 0, 200, 400)


def test_vstack_with_hstack_children():
    """VStack[HStack(h=50), HStack(h=80)] — each gets full width."""
    vs = VStack()
    hs1 = HStack()
    hs1.preferred_height = px(50)
    hs2 = HStack()
    hs2.preferred_height = px(80)
    vs.add_child(hs1)
    vs.add_child(hs2)

    vs.layout(0, 0, 500, 400, VIEWPORT_W, VIEWPORT_H)
    assert_rect(hs1, 0, 0, 500, 50)
    assert_rect(hs2, 0, 50, 500, 80)


# --- Editor-like scenarios ---

def test_editor_three_columns():
    """HStack[left(250), canvas(stretch), right(220)]"""
    hs = HStack()
    left = make_widget(250)
    canvas = make_widget(stretch=True)
    right = make_widget(220)
    hs.add_child(left)
    hs.add_child(canvas)
    hs.add_child(right)

    hs.layout(0, 0, 1280, 700, VIEWPORT_W, VIEWPORT_H)
    assert_rect(left, 0, 0, 250, 700)
    assert_rect(canvas, 250, 0, 810, 700)
    assert_rect(right, 1060, 0, 220, 700)


def test_editor_with_splitters():
    """HStack[left(250), spl(5), canvas(stretch), spl(5), right(220)]"""
    hs = HStack()
    left = make_widget(250)
    spl1 = Splitter(target=left, side="left")
    canvas = make_widget(stretch=True)
    right = make_widget(220)
    spl2 = Splitter(target=right, side="right")

    hs.add_child(left)
    hs.add_child(spl1)
    hs.add_child(canvas)
    hs.add_child(spl2)
    hs.add_child(right)

    hs.layout(0, 0, 1280, 700, VIEWPORT_W, VIEWPORT_H)
    # canvas.width = 1280 - 250 - 5 - 5 - 220 = 800
    assert_rect(left, 0, 0, 250, 700)
    assert abs(spl1.x - 250) <= 0.5
    assert abs(spl1.width - 5) <= 0.5
    assert abs(canvas.width - 800) <= 0.5
    assert abs(right.width - 220) <= 0.5


def test_vstack_stretch_scroll_area():
    """VStack(h=600)[fixed(30), fixed(30), ScrollArea(stretch)]"""
    vs = VStack()
    top1 = make_widget(0, 30)
    top2 = make_widget(0, 30)
    sa = ScrollArea()
    sa.stretch = True

    vs.add_child(top1)
    vs.add_child(top2)
    vs.add_child(sa)

    vs.layout(0, 0, 400, 600, VIEWPORT_W, VIEWPORT_H)
    assert_rect(top1, 0, 0, 400, 30)
    assert_rect(top2, 0, 30, 400, 30)
    assert_rect(sa, 0, 60, 400, 540)


def test_menubar_toolbar_content():
    """VStack[Menu(30), Tool(40), HStack(stretch)] at 1280x800"""
    vs = VStack()
    menu = make_widget(0, 30)
    toolbar = make_widget(0, 40)
    content = HStack()
    content.stretch = True
    vs.add_child(menu)
    vs.add_child(toolbar)
    vs.add_child(content)

    vs.layout(0, 0, 1280, 800, VIEWPORT_W, VIEWPORT_H)
    assert_rect(menu, 0, 0, 1280, 30)
    assert_rect(toolbar, 0, 30, 1280, 40)
    assert_rect(content, 0, 70, 1280, 730)


def test_full_editor_skeleton():
    """Full editor layout:
    VStack(1280x800)
    ├── menu (h=30)
    ├── toolbar (h=40)
    ├── HStack (stretch)
    │   ├── left (w=250)
    │   ├── splitter (w=5)
    │   ├── canvas (stretch)
    │   ├── splitter (w=5)
    │   └── right (w=220)
    └── statusbar (h=24)
    """
    root = VStack()
    menu = make_widget(0, 30)
    toolbar = make_widget(0, 40)

    main_area = HStack()
    main_area.stretch = True
    left = make_widget(250)
    spl_l = Splitter(target=left, side="left")
    canvas = make_widget(stretch=True)
    right = make_widget(220)
    spl_r = Splitter(target=right, side="right")
    main_area.add_child(left)
    main_area.add_child(spl_l)
    main_area.add_child(canvas)
    main_area.add_child(spl_r)
    main_area.add_child(right)

    statusbar = make_widget(0, 24)

    root.add_child(menu)
    root.add_child(toolbar)
    root.add_child(main_area)
    root.add_child(statusbar)

    root.layout(0, 0, 1280, 800, VIEWPORT_W, VIEWPORT_H)

    # VStack: menu(30) + toolbar(40) + statusbar(24) = 94 fixed
    # main_area stretch = 800 - 94 = 706
    assert_rect(menu, 0, 0, 1280, 30)
    assert_rect(toolbar, 0, 30, 1280, 40)
    assert_rect(main_area, 0, 70, 1280, 706)
    assert_rect(statusbar, 0, 776, 1280, 24)

    # HStack inside main_area:
    # left(250) + spl(5) + canvas(stretch) + spl(5) + right(220)
    # canvas.w = 1280 - 250 - 5 - 5 - 220 = 800
    assert abs(canvas.width - 800) <= 0.5
    assert abs(canvas.height - 706) <= 0.5
    assert abs(left.x - 0) <= 0.5
    assert abs(canvas.x - 255) <= 0.5


# --- Edge cases ---

def test_all_stretch():
    """VStack with 3 stretch children — each gets h/3."""
    vs = VStack()
    c1 = make_widget(stretch=True)
    c2 = make_widget(stretch=True)
    c3 = make_widget(stretch=True)
    vs.add_child(c1)
    vs.add_child(c2)
    vs.add_child(c3)

    vs.layout(0, 0, 400, 600, VIEWPORT_W, VIEWPORT_H)
    assert abs(c1.height - 200) <= 0.5
    assert abs(c2.height - 200) <= 0.5
    assert abs(c3.height - 200) <= 0.5


def test_overflow_fixed_exceeds_container():
    """VStack(h=100) with two 60px children — remaining=0, doesn't crash."""
    vs = VStack()
    c1 = make_widget(0, 60)
    c2 = make_widget(0, 60)
    vs.add_child(c1)
    vs.add_child(c2)

    vs.layout(0, 0, 400, 100, VIEWPORT_W, VIEWPORT_H)
    assert_rect(c1, 0, 0, 400, 60)
    assert_rect(c2, 0, 60, 400, 60)


def test_splitter_relayout():
    """After splitter drag, relayout produces correct sizes."""
    hs = HStack()
    left = make_widget(250)
    spl = Splitter(target=left, side="left")
    canvas = make_widget(stretch=True)
    hs.add_child(left)
    hs.add_child(spl)
    hs.add_child(canvas)

    # Initial layout
    hs.layout(0, 0, 1000, 600, VIEWPORT_W, VIEWPORT_H)
    assert abs(left.width - 250) <= 0.5
    assert abs(canvas.width - 745) <= 0.5  # 1000 - 250 - 5

    # Simulate drag: for side="left", dragging right shrinks left panel
    ev_down = MouseEvent(x=250, y=300, button=MouseButton.LEFT)
    spl.on_mouse_down(ev_down)
    ev_move = MouseEvent(x=400, y=300)
    spl.on_mouse_move(ev_move)

    # Re-layout
    hs.layout(0, 0, 1000, 600, VIEWPORT_W, VIEWPORT_H)
    new_left_w = left.preferred_width.to_pixels(VIEWPORT_W)
    assert abs(new_left_w - 100) <= 0.5
    assert abs(left.width - 100) <= 0.5
    assert abs(canvas.width - 895) <= 0.5  # 1000 - 100 - 5
