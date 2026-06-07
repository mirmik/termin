"""Shared tcgui helpers for CSG editor panels."""

from __future__ import annotations

from typing import Callable

from tcgui.widgets.button import Button
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.panel import Panel
from tcgui.widgets.separator import Separator
from tcgui.widgets.spin_box import SpinBox
from tcgui.widgets.units import px


COLOR_PANEL = (0.10, 0.105, 0.12, 1.0)
COLOR_TITLE = (0.84, 0.88, 0.94, 1.0)
COLOR_GROUP = (0.70, 0.74, 0.80, 1.0)
COLOR_MUTED = (0.58, 0.64, 0.72, 1.0)


def make_button(text: str, callback) -> Button:
    button = Button()
    button.text = text
    button.on_click = callback
    return button


def make_separator() -> Separator:
    separator = Separator()
    separator.orientation = "horizontal"
    return separator


def make_label(text: str, color=COLOR_MUTED, width: int | None = None) -> Label:
    label = Label()
    label.text = text
    label.color = color
    if width is not None:
        label.preferred_width = px(width)
    return label


def clear_children(panel: Panel) -> None:
    for child in panel.children[:]:
        panel.remove_child(child)


def style_param_panel(panel: Panel) -> None:
    panel.padding = 8
    panel.background_color = COLOR_PANEL
    panel.visible = False


def set_visible(panel: Panel, visible: bool, request_layout: Callable[[], None]) -> None:
    if panel.visible == visible:
        return
    panel.visible = visible
    request_layout()


def make_spin_box(
    value: float,
    on_changed,
    *,
    decimals: int = 3,
    step: float = 0.1,
    min_value: float = -1000000.0,
    max_value: float = 1000000.0,
) -> SpinBox:
    spin = SpinBox()
    spin.decimals = decimals
    spin.step = step
    spin.min_value = min_value
    spin.max_value = max_value
    spin.preferred_height = px(24)
    spin.stretch = True
    spin.value = value
    spin.on_changed = on_changed
    return spin


def make_number_row(
    label_text: str,
    value: float,
    on_changed,
    *,
    decimals: int = 3,
    step: float = 0.1,
    min_value: float = -1000000.0,
    max_value: float = 1000000.0,
    label_width: int = 82,
) -> tuple[HStack, SpinBox]:
    row = HStack()
    row.spacing = 6
    row.preferred_height = px(26)
    row.add_child(make_label(label_text, width=label_width))

    spin = make_spin_box(
        value,
        on_changed,
        decimals=decimals,
        step=step,
        min_value=min_value,
        max_value=max_value,
    )
    row.add_child(spin)
    return row, spin


def param_vec3(params: dict, key: str, default: tuple[float, float, float]) -> tuple[float, float, float]:
    value = params.get(key, default)
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except Exception:
        return default


def param_float(params: dict, key: str, default: float) -> float:
    try:
        return float(params.get(key, default))
    except Exception:
        return default


__all__ = [
    "COLOR_GROUP",
    "COLOR_MUTED",
    "COLOR_TITLE",
    "clear_children",
    "make_button",
    "make_label",
    "make_number_row",
    "make_separator",
    "make_spin_box",
    "param_float",
    "param_vec3",
    "set_visible",
    "style_param_panel",
]
