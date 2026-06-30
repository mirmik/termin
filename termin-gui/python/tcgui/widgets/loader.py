"""YAML loader for the widget-based UI system."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, Type
import yaml

from tcgui.widgets.widget import Widget
from tcgui.widgets.containers import HStack, VStack, Panel, ScrollArea, GroupBox
from tcgui.widgets.basic import (
    Button,
    Checkbox,
    ComboBox,
    IconButton,
    ImageWidget,
    Label,
    ProgressBar,
    RichTextView,
    Separator,
    Slider,
    SliderEdit,
    SpinBox,
    TextArea,
    TextInput,
)
from tcgui.widgets.file_grid_widget import FileGridWidget
from tcgui.widgets.tree import TreeNode, TreeWidget
from tcgui.widgets.tabs import TabBar, TabView
from tcgui.widgets.menu import MenuItem, Menu
from tcgui.widgets.menu_bar import MenuBar
from tcgui.widgets.tool_bar import ToolBar
from tcgui.widgets.status_bar import StatusBar
from tcgui.widgets.dialog import Dialog
from tcgui.widgets.message_box import MessageBox
from tcgui.widgets.canvas import Canvas
from tcgui.widgets.color_dialog import ColorDialog
from tcgui.widgets.units import Value


AttributeConverter = Callable[["UILoader", Any], Any]


def _identity(_loader: "UILoader", value: Any) -> Any:
    return value


def _as_float(_loader: "UILoader", value: Any) -> float:
    return float(value)


def _as_int(_loader: "UILoader", value: Any) -> int:
    return int(value)


def _as_bool(_loader: "UILoader", value: Any) -> bool:
    return bool(value)


def _as_str(_loader: "UILoader", value: Any) -> str:
    return str(value)


def _as_list(_loader: "UILoader", value: Any) -> list[Any]:
    return list(value)


def _as_color(loader: "UILoader", value: Any) -> tuple[float, float, float, float]:
    return loader._parse_color(value)


@dataclass(frozen=True)
class AttributeSpec:
    key: str
    target: str | None = None
    converter: AttributeConverter = _identity

    def apply(self, loader: "UILoader", widget: Widget, data: dict[str, Any]) -> None:
        if self.key in data:
            setattr(widget, self.target or self.key, self.converter(loader, data[self.key]))


WidgetMatcher = type[Widget] | tuple[type[Widget], ...]


def _attrs(*keys: str, converter: AttributeConverter = _identity) -> tuple[AttributeSpec, ...]:
    return tuple(AttributeSpec(key, converter=converter) for key in keys)


COMMON_WIDGET_KEYS = {
    "type",
    "name",
    "visible",
    "enabled",
    "size",
    "width",
    "height",
    "anchor",
    "offset_x",
    "offset_y",
    "offset",
    "position_x",
    "position_y",
    "position",
    "children",
}


ATTRIBUTE_SPECS: tuple[tuple[WidgetMatcher, tuple[AttributeSpec, ...]], ...] = (
    ((HStack, VStack), (
        *_attrs("spacing", converter=_as_float),
        *_attrs("alignment", "justify"),
    )),
    (ScrollArea, (
        *_attrs("scroll_speed", "scrollbar_width", converter=_as_float),
        *_attrs("show_scrollbar", converter=_as_bool),
        *_attrs("scrollbar_color", "scrollbar_hover_color", converter=_as_color),
    )),
    (Panel, (
        *_attrs("padding", "border_radius", converter=_as_float),
        *_attrs("background_color", "background_tint", converter=_as_color),
        *_attrs("background_image", converter=_as_str),
    )),
    (Label, (
        *_attrs("text", "alignment"),
        *_attrs("color", converter=_as_color),
        *_attrs("font_size", converter=_as_float),
    )),
    (Button, (
        *_attrs("text", "icon"),
        *_attrs("background_color", "hover_color", "pressed_color", "text_color", converter=_as_color),
        *_attrs("border_radius", "font_size", "padding", converter=_as_float),
    )),
    (Checkbox, (
        *_attrs("text"),
        *_attrs("checked", converter=_as_bool),
        *_attrs("box_color", "check_color", "hover_color", "text_color", converter=_as_color),
        *_attrs("border_radius", "font_size", "box_size", "spacing", converter=_as_float),
    )),
    (IconButton, (
        *_attrs("icon", "tooltip"),
        *_attrs(
            "background_color",
            "hover_color",
            "pressed_color",
            "active_color",
            "icon_color",
            converter=_as_color,
        ),
        *_attrs("border_radius", "size", "font_size", converter=_as_float),
        *_attrs("active", converter=_as_bool),
    )),
    (TextInput, (
        *_attrs("text", "placeholder", converter=_as_str),
        *_attrs("font_size", "padding", "border_radius", "border_width", converter=_as_float),
        *_attrs(
            "background_color",
            "focused_background_color",
            "border_color",
            "focused_border_color",
            "text_color",
            "placeholder_color",
            "cursor_color",
            converter=_as_color,
        ),
    )),
    (ProgressBar, (
        *_attrs("value", "border_radius", "font_size", converter=_as_float),
        *_attrs("show_text", converter=_as_bool),
        *_attrs("background_color", "fill_color", "text_color", converter=_as_color),
    )),
    (Slider, (
        *_attrs(
            "value",
            "min_value",
            "max_value",
            "step",
            "track_height",
            "thumb_radius",
            "border_radius",
            converter=_as_float,
        ),
        *_attrs("track_color", "fill_color", "thumb_color", "thumb_hover_color", converter=_as_color),
    )),
    (ComboBox, (
        *_attrs("items", converter=_as_list),
        *_attrs("selected_index", converter=_as_int),
        *_attrs("placeholder", converter=_as_str),
        *_attrs("background_color", "border_color", "text_color", converter=_as_color),
        *_attrs("font_size", "border_radius", converter=_as_float),
    )),
    (ImageWidget, (
        *_attrs("image_path", converter=_as_str),
        *_attrs("tint", converter=_as_color),
    )),
    (Separator, (
        *_attrs("orientation"),
        *_attrs("color", converter=_as_color),
        *_attrs("thickness", "margin", converter=_as_float),
    )),
    (TreeNode, (
        *_attrs("expanded", converter=_as_bool),
    )),
    (TreeWidget, (
        *_attrs("indent_size", "toggle_size", "row_height", "row_spacing", converter=_as_float),
        *_attrs("selected_background", "hover_background", "toggle_color", converter=_as_color),
    )),
    (TabBar, (
        *_attrs("tabs", converter=_as_list),
        *_attrs("selected_index", converter=_as_int),
        *_attrs("tab_padding", "tab_spacing", "font_size", "indicator_height", "border_radius", converter=_as_float),
        *_attrs(
            "tab_color",
            "selected_tab_color",
            "hover_tab_color",
            "text_color",
            "selected_text_color",
            "indicator_color",
            converter=_as_color,
        ),
    )),
    (TabView, (
        *_attrs("tab_position"),
    )),
    (Menu, (
        *_attrs(
            "background_color",
            "item_hover_color",
            "text_color",
            "shortcut_color",
            "icon_color",
            "separator_color",
            converter=_as_color,
        ),
        *_attrs("border_radius", "font_size", "item_height", converter=_as_float),
    )),
    (SpinBox, (
        *_attrs(
            "value",
            "min_value",
            "max_value",
            "step",
            "font_size",
            "padding",
            "button_width",
            converter=_as_float,
        ),
        *_attrs("decimals", converter=_as_int),
        *_attrs("border_radius", "border_width", converter=_as_float),
    )),
    (SliderEdit, (
        *_attrs("value", "min_value", "max_value", "step", "spacing", "spinbox_width", converter=_as_float),
        *_attrs("decimals", converter=_as_int),
    )),
    (TextArea, (
        *_attrs("text", "placeholder", converter=_as_str),
        *_attrs("max_lines", converter=_as_int),
        *_attrs("read_only", "show_scrollbar", converter=_as_bool),
        *_attrs(
            "line_height",
            "font_size",
            "padding",
            "border_radius",
            "border_width",
            "scrollbar_width",
            converter=_as_float,
        ),
    )),
    (RichTextView, (
        *_attrs("text", "placeholder", converter=_as_str),
        *_attrs("word_wrap", "show_scrollbar", converter=_as_bool),
        *_attrs(
            "line_height",
            "font_size",
            "padding",
            "border_radius",
            "border_width",
            "scrollbar_width",
            converter=_as_float,
        ),
    )),
    (MenuBar, (
        *_attrs("background_color", "text_color", "hover_color", "active_color", converter=_as_color),
        *_attrs("font_size", "item_padding_x", "item_padding_y", converter=_as_float),
    )),
    (ToolBar, (
        *_attrs(
            "background_color",
            "item_hover_color",
            "icon_color",
            "text_color",
            "separator_color",
            converter=_as_color,
        ),
        *_attrs("border_radius", "font_size", "item_size", converter=_as_float),
    )),
    (StatusBar, (
        *_attrs("background_color", "text_color", "temp_text_color", converter=_as_color),
        *_attrs("font_size", "padding_x", converter=_as_float),
    )),
    (Dialog, (
        *_attrs("title", converter=_as_str),
        *_attrs("background_color", "title_background_color", converter=_as_color),
        *_attrs("border_radius", "padding", "min_width", converter=_as_float),
    )),
    (GroupBox, (
        *_attrs("title", converter=_as_str),
        *_attrs("expanded", converter=_as_bool),
        *_attrs("title_height", "content_padding", "title_padding", "font_size", "border_radius", converter=_as_float),
        *_attrs(
            "background_color",
            "title_background_color",
            "title_hover_color",
            "title_text_color",
            "arrow_color",
            "border_color",
            converter=_as_color,
        ),
    )),
    (Canvas, (
        *_attrs("background_color", converter=_as_color),
        *_attrs("min_zoom", "max_zoom", "zoom_factor", converter=_as_float),
    )),
)


STRUCTURAL_ATTRIBUTE_KEYS: tuple[tuple[WidgetMatcher, set[str]], ...] = (
    (TreeNode, {"nodes", "content"}),
    (TreeWidget, {"nodes"}),
    (TabView, {"tabs"}),
    (Menu, {"items"}),
    (RichTextView, {"html"}),
    (StatusBar, {"text"}),
)


class UILoader:
    """Loads UI widget trees from YAML files."""

    # Registry of widget types
    WIDGET_TYPES: dict[str, Type[Widget]] = {
        "HStack": HStack,
        "VStack": VStack,
        "Panel": Panel,
        "ScrollArea": ScrollArea,
        "Label": Label,
        "Button": Button,
        "Checkbox": Checkbox,
        "IconButton": IconButton,
        "Separator": Separator,
        "Image": ImageWidget,
        "TextInput": TextInput,
        "FileGridWidget": FileGridWidget,
        "ProgressBar": ProgressBar,
        "Slider": Slider,
        "ComboBox": ComboBox,
        "TreeNode": TreeNode,
        "TreeWidget": TreeWidget,
        "TabBar": TabBar,
        "TabView": TabView,
        "Menu": Menu,
        "MenuBar": MenuBar,
        "ToolBar": ToolBar,
        "StatusBar": StatusBar,
        "Dialog": Dialog,
        "MessageBox": MessageBox,
        "SpinBox": SpinBox,
        "SliderEdit": SliderEdit,
        "TextArea": TextArea,
        "RichTextView": RichTextView,
        "GroupBox": GroupBox,
        "Canvas": Canvas,
        "ColorDialog": ColorDialog,
    }

    def __init__(self):
        # Custom widget types can be registered here
        self._custom_types: dict[str, Type[Widget]] = {}

    def register_type(self, name: str, cls: Type[Widget]):
        """Register a custom widget type."""
        self._custom_types[name] = cls

    def load(self, path: str) -> Widget:
        """Load UI from a YAML file."""
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return self._parse_widget(data.get("root", data))

    def load_string(self, yaml_str: str) -> Widget:
        """Load UI from a YAML string."""
        data = yaml.safe_load(yaml_str)
        return self._parse_widget(data.get("root", data))

    def _get_widget_class(self, type_name: str) -> Type[Widget]:
        """Get widget class by type name."""
        if type_name in self._custom_types:
            return self._custom_types[type_name]
        if type_name in self.WIDGET_TYPES:
            return self.WIDGET_TYPES[type_name]
        raise ValueError(f"Unknown widget type: {type_name}")

    def _parse_widget(self, data: dict) -> Widget:
        """Parse a widget from a dictionary."""
        widget_type = data.get("type")
        if not widget_type:
            raise ValueError("Widget must have a 'type' field")

        cls = self._get_widget_class(widget_type)
        widget = cls()

        # Common attributes
        if "name" in data:
            widget.name = data["name"]

        if "visible" in data:
            widget.visible = data["visible"]

        if "enabled" in data:
            widget.enabled = data["enabled"]

        # Size (can be [w, h] or {width: ..., height: ...})
        if "size" in data:
            size = data["size"]
            if isinstance(size, list) and len(size) == 2:
                widget.preferred_width = Value.parse(size[0])
                widget.preferred_height = Value.parse(size[1])
            elif isinstance(size, dict):
                if "width" in size:
                    widget.preferred_width = Value.parse(size["width"])
                if "height" in size:
                    widget.preferred_height = Value.parse(size["height"])

        if "width" in data:
            widget.preferred_width = Value.parse(data["width"])

        if "height" in data:
            widget.preferred_height = Value.parse(data["height"])

        # Anchor positioning (for root widget)
        if "anchor" in data:
            widget.anchor = data["anchor"]

        if "offset_x" in data:
            widget.offset_x = float(data["offset_x"])

        if "offset_y" in data:
            widget.offset_y = float(data["offset_y"])

        # Shorthand: offset: [x, y]
        if "offset" in data:
            offset = data["offset"]
            if isinstance(offset, (list, tuple)) and len(offset) == 2:
                widget.offset_x = float(offset[0])
                widget.offset_y = float(offset[1])

        # Absolute positioning (for anchor="absolute")
        if "position_x" in data:
            widget.position_x = Value.parse(data["position_x"])

        if "position_y" in data:
            widget.position_y = Value.parse(data["position_y"])

        # Shorthand: position: [x, y]
        if "position" in data:
            pos = data["position"]
            if isinstance(pos, (list, tuple)) and len(pos) == 2:
                widget.position_x = Value.parse(pos[0])
                widget.position_y = Value.parse(pos[1])

        # Type-specific attributes
        self._apply_attributes(widget, data)

        # Children
        if "children" in data:
            for child_data in data["children"]:
                child = self._parse_widget(child_data)
                widget.add_child(child)

        return widget

    def _apply_attributes(self, widget: Widget, data: dict):
        """Apply type-specific attributes to a widget."""

        specs = tuple(self._attribute_specs_for(widget))
        for spec in specs:
            spec.apply(self, widget, data)

        self._apply_structural_attributes(widget, data)
        self._validate_supported_attributes(widget, data, specs)

    def _attribute_specs_for(self, widget: Widget) -> Iterable[AttributeSpec]:
        for widget_type, specs in ATTRIBUTE_SPECS:
            if isinstance(widget, widget_type):
                yield from specs

    def _structural_keys_for(self, widget: Widget) -> set[str]:
        keys: set[str] = set()
        for widget_type, widget_keys in STRUCTURAL_ATTRIBUTE_KEYS:
            if isinstance(widget, widget_type):
                keys.update(widget_keys)
        return keys

    def _validate_supported_attributes(
        self,
        widget: Widget,
        data: dict,
        specs: Iterable[AttributeSpec],
    ) -> None:
        if any(isinstance(widget, custom_type) for custom_type in self._custom_types.values()):
            return

        supported = set(COMMON_WIDGET_KEYS)
        supported.update(spec.key for spec in specs)
        supported.update(self._structural_keys_for(widget))
        unsupported = sorted(set(data) - supported)
        if unsupported:
            keys = ", ".join(unsupported)
            raise ValueError(f"Unsupported attribute(s) for {type(widget).__name__}: {keys}")

    def _apply_structural_attributes(self, widget: Widget, data: dict) -> None:
        if isinstance(widget, TreeNode):
            if "nodes" in data:
                for node_data in data["nodes"]:
                    child_node = self._parse_widget(node_data)
                    if isinstance(child_node, TreeNode):
                        widget.add_node(child_node)
            if "content" in data:
                widget.content = self._parse_widget(data["content"])

        if isinstance(widget, TreeWidget) and "nodes" in data:
            for node_data in data["nodes"]:
                child_node = self._parse_widget(node_data)
                if isinstance(child_node, TreeNode):
                    widget.add_root(child_node)

        if isinstance(widget, TabView) and "tabs" in data:
            for tab_data in data["tabs"]:
                if not isinstance(tab_data, dict):
                    raise ValueError("TabView tabs must be objects")
                title = tab_data.get("title", "")
                if "content" in tab_data:
                    content = self._parse_widget(tab_data["content"])
                    widget.add_tab(title, content)

        if isinstance(widget, Menu) and "items" in data:
            items = []
            for item_data in data["items"]:
                if isinstance(item_data, str) and item_data == "---":
                    items.append(MenuItem.sep())
                elif isinstance(item_data, dict):
                    items.append(MenuItem(
                        label=item_data.get("label", ""),
                        icon=item_data.get("icon"),
                        shortcut=item_data.get("shortcut"),
                        enabled=item_data.get("enabled", True),
                        separator=item_data.get("separator", False),
                    ))
                else:
                    raise ValueError("Menu items must be objects or '---' separators")
            widget.items = items

        if isinstance(widget, RichTextView) and "html" in data:
            widget.set_html(str(data["html"]))

        if isinstance(widget, StatusBar) and "text" in data:
            widget.set_text(str(data["text"]))

    def _parse_color(self, value) -> tuple[float, float, float, float]:
        """Parse a color from various formats."""
        if isinstance(value, (list, tuple)):
            if len(value) == 3:
                return (float(value[0]), float(value[1]), float(value[2]), 1.0)
            elif len(value) == 4:
                return (float(value[0]), float(value[1]), float(value[2]), float(value[3]))

        if isinstance(value, str):
            # Hex color
            if value.startswith("#"):
                hex_str = value[1:]
                if len(hex_str) == 6:
                    r = int(hex_str[0:2], 16) / 255.0
                    g = int(hex_str[2:4], 16) / 255.0
                    b = int(hex_str[4:6], 16) / 255.0
                    return (r, g, b, 1.0)
                elif len(hex_str) == 8:
                    r = int(hex_str[0:2], 16) / 255.0
                    g = int(hex_str[2:4], 16) / 255.0
                    b = int(hex_str[4:6], 16) / 255.0
                    a = int(hex_str[6:8], 16) / 255.0
                    return (r, g, b, a)

        raise ValueError(f"Cannot parse color: {value}")
