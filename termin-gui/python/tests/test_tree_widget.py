"""TreeWidget scrolling tests."""

from tcbase import MouseButton
from tcgui.widgets.events import MouseEvent, MouseWheelEvent
from tcgui.widgets.tree import TreeNode, TreeWidget


def _make_tree(count: int) -> TreeWidget:
    tree = TreeWidget()
    tree.row_height = 10.0
    tree.row_spacing = 0.0
    for _ in range(count):
        tree.add_root(TreeNode())
    tree.layout(0.0, 0.0, 100.0, 50.0, 100.0, 50.0)
    return tree


def test_tree_scrollbar_visible_when_content_overflows() -> None:
    tree = _make_tree(20)

    assert tree._has_scrollbar()


def test_tree_scrollbar_drag_updates_scroll_offset() -> None:
    tree = _make_tree(20)

    assert tree.on_mouse_down(MouseEvent(98.0, 5.0, MouseButton.LEFT))
    tree.on_mouse_move(MouseEvent(98.0, 35.0, MouseButton.LEFT))

    assert tree._scroll_offset > 0.0


def test_tree_wheel_scrolls_to_same_model_as_scrollbar() -> None:
    tree = _make_tree(20)

    assert tree.on_mouse_wheel(MouseWheelEvent(0.0, -1.0, 10.0, 10.0))
    assert tree._scroll_offset == 30.0
