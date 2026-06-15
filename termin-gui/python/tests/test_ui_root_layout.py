"""Root widget layout tests."""

from tcgui.widgets.panel import Panel
from tcgui.widgets.ui import UI
from tcgui.widgets.units import pct, px
from tests.conftest import assert_rect, make_widget


def _layout_only_ui(root) -> UI:
    ui = UI.__new__(UI)
    ui._root = root
    ui._viewport_w = 0
    ui._viewport_h = 0
    return ui


def test_ui_root_uses_computed_size_for_anchored_overlay() -> None:
    root = Panel()
    root.anchor = "top-right"
    root.offset_x = -10
    root.offset_y = 12
    root.padding = 8
    root.add_child(make_widget(120, 40))
    ui = _layout_only_ui(root)

    ui.layout(800, 600)

    assert_rect(root, 800 - 136 - 10, 12, 136, 56)


def test_ui_root_can_still_fill_viewport_explicitly() -> None:
    root = Panel()
    root.preferred_width = pct(100)
    root.preferred_height = pct(100)
    root.add_child(make_widget(120, 40))
    ui = _layout_only_ui(root)

    ui.layout(800, 600)

    assert_rect(root, 0, 0, 800, 600)


def test_ui_root_falls_back_to_viewport_for_zero_intrinsic_size() -> None:
    root = Panel()
    root.preferred_width = px(0)
    root.preferred_height = px(0)
    ui = _layout_only_ui(root)

    ui.layout(800, 600)

    assert_rect(root, 0, 0, 800, 600)
