"""Menu widget tests."""

from tcgui.widgets.events import MouseWheelEvent
from tcgui.widgets.menu import Menu, MenuItem


class _UIStub:
    def __init__(self, width: int = 400, height: int = 300):
        self._viewport_w = width
        self._viewport_h = height
        self.overlay = None

    def show_overlay(self, widget, **_kwargs):
        self.overlay = widget
        widget._ui = self


def _make_menu(count: int) -> Menu:
    menu = Menu()
    menu.items = [MenuItem(f"Component{i}") for i in range(count)]
    return menu


def test_menu_show_clamps_height_to_viewport():
    ui = _UIStub(width=400, height=300)
    menu = _make_menu(50)

    menu.show(ui, 350, 250)

    assert menu.x + menu.width <= ui._viewport_w
    assert menu.y + menu.height <= ui._viewport_h
    assert menu.height <= ui._viewport_h - menu.viewport_margin * 2
    assert menu._max_scroll() > 0


def test_menu_wheel_scrolls_item_lookup():
    ui = _UIStub(width=400, height=120)
    menu = _make_menu(20)
    menu.show(ui, 10, 10)

    before = menu._index_at(menu.y + menu.padding_y + 1)

    assert menu.on_mouse_wheel(MouseWheelEvent(0, -1, menu.x + 10, menu.y + 10)) is True

    after = menu._index_at(menu.y + menu.padding_y + 1)
    assert menu._scroll_offset == menu.scroll_speed
    assert after > before
