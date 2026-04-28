"""ListWidget tests."""

from tcgui.widgets.events import MouseWheelEvent
from tcgui.widgets.list_widget import ListWidget


def _make_items(count: int) -> list[dict]:
    return [{"text": f"item {i}"} for i in range(count)]


def test_wheel_does_not_consume_when_laid_out_to_content_height():
    lst = ListWidget()
    lst.item_height = 28
    lst.item_spacing = 2
    lst.set_items(_make_items(10))

    width, height = lst.compute_size(400, 300)
    lst.layout(0, 0, width, height, 400, 300)

    assert lst.on_mouse_wheel(MouseWheelEvent(0, -1, 10, 10)) is False
    assert lst._scroll_offset == 0.0


def test_wheel_scrolls_when_viewport_is_shorter_than_content():
    lst = ListWidget()
    lst.item_height = 28
    lst.item_spacing = 2
    lst.set_items(_make_items(10))
    lst.layout(0, 0, 400, 100, 400, 300)

    assert lst.on_mouse_wheel(MouseWheelEvent(0, -1, 10, 10)) is True
    assert lst._scroll_offset == 30.0
