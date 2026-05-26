"""FileGridWidget scrolling tests."""

from tcbase import MouseButton
from tcgui.widgets.events import MouseEvent, MouseWheelEvent
from tcgui.widgets.file_grid_widget import FileGridWidget
from tcgui.widgets.hstack import HStack
from tcgui.widgets.units import px
from tcgui.widgets.vstack import VStack


def _make_items(count: int) -> list[dict]:
    return [{"text": f"file {i}", "subtitle": ".txt"} for i in range(count)]


def _make_grid(count: int) -> FileGridWidget:
    grid = FileGridWidget()
    grid.tile_width = 50.0
    grid.tile_height = 20.0
    grid.tile_spacing = 0.0
    grid.padding = 0.0
    grid.set_items(_make_items(count))
    grid.layout(0.0, 0.0, 60.0, 100.0, 60.0, 100.0)
    return grid


def test_file_grid_scrollbar_visible_when_content_overflows() -> None:
    grid = _make_grid(20)

    assert grid._has_scrollbar()


def test_file_grid_scrollbar_drag_updates_scroll_offset_without_selecting_item() -> None:
    grid = _make_grid(20)

    assert grid.on_mouse_down(MouseEvent(58.0, 5.0, MouseButton.LEFT))
    grid.on_mouse_move(MouseEvent(58.0, 35.0, MouseButton.LEFT))

    assert grid._scroll_offset > 0.0
    assert grid.selected_index == -1


def test_file_grid_wheel_scrolls_to_same_model_as_scrollbar() -> None:
    grid = _make_grid(20)

    assert grid.on_mouse_wheel(MouseWheelEvent(0.0, -1.0, 10.0, 10.0))
    assert grid._scroll_offset == 30.0


def test_file_grid_stretches_to_remaining_vstack_height_with_zero_preferred_height() -> None:
    column = VStack()
    column.spacing = 4.0

    breadcrumb = HStack()
    breadcrumb.preferred_height = px(24.0)

    grid = FileGridWidget()
    grid.tile_width = 50.0
    grid.tile_height = 20.0
    grid.tile_spacing = 0.0
    grid.padding = 0.0
    grid.stretch = True
    grid.preferred_height = px(0.0)
    grid.set_items(_make_items(20))

    column.add_child(breadcrumb)
    column.add_child(grid)
    column.layout(0.0, 0.0, 60.0, 100.0, 60.0, 100.0)

    assert grid.height == 72.0
    assert grid._has_scrollbar()
