"""YAML loader for the widget-based UI system."""

from __future__ import annotations

from typing import Type
import yaml

from tcgui.widgets.widget import Widget
from tcgui.widgets.containers import HStack, VStack, Panel, ScrollArea, GroupBox
from tcgui.widgets.basic import Label, Button, Checkbox, IconButton, Separator, ImageWidget, TextInput, ProgressBar, Slider, ComboBox, SpinBox, SliderEdit, TextArea
from tcgui.widgets.tree import TreeNode, TreeWidget
from tcgui.widgets.tabs import TabBar, TabView
from tcgui.widgets.menu import MenuItem, Menu
from tcgui.widgets.menu_bar import MenuBar
from tcgui.widgets.tool_bar import ToolBar, ToolBarItem
from tcgui.widgets.status_bar import StatusBar
from tcgui.widgets.dialog import Dialog
from tcgui.widgets.message_box import MessageBox
from tcgui.widgets.canvas import Canvas
from tcgui.widgets.color_dialog import ColorDialog
from tcgui.widgets.units import Value


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

        # Container attributes
        if isinstance(widget, (HStack, VStack)):
            if "spacing" in data:
                widget.spacing = float(data["spacing"])
            if "alignment" in data:
                widget.alignment = data["alignment"]
            if "justify" in data:
                widget.justify = data["justify"]

        # ScrollArea attributes
        if isinstance(widget, ScrollArea):
            if "scroll_speed" in data:
                widget.scroll_speed = float(data["scroll_speed"])
            if "show_scrollbar" in data:
                widget.show_scrollbar = bool(data["show_scrollbar"])
            if "scrollbar_width" in data:
                widget.scrollbar_width = float(data["scrollbar_width"])
            if "scrollbar_color" in data:
                widget.scrollbar_color = self._parse_color(data["scrollbar_color"])
            if "scrollbar_hover_color" in data:
                widget.scrollbar_hover_color = self._parse_color(data["scrollbar_hover_color"])

        # Panel attributes
        if isinstance(widget, Panel):
            if "padding" in data:
                widget.padding = float(data["padding"])
            if "background_color" in data:
                widget.background_color = self._parse_color(data["background_color"])
            if "border_radius" in data:
                widget.border_radius = float(data["border_radius"])
            if "background_image" in data:
                widget.background_image = str(data["background_image"])
            if "background_tint" in data:
                widget.background_tint = self._parse_color(data["background_tint"])

        # Label attributes
        if isinstance(widget, Label):
            if "text" in data:
                widget.text = data["text"]
            if "color" in data:
                widget.color = self._parse_color(data["color"])
            if "font_size" in data:
                widget.font_size = float(data["font_size"])
            if "alignment" in data:
                widget.alignment = data["alignment"]

        # Button attributes
        if isinstance(widget, Button):
            if "text" in data:
                widget.text = data["text"]
            if "icon" in data:
                widget.icon = data["icon"]
            if "background_color" in data:
                widget.background_color = self._parse_color(data["background_color"])
            if "hover_color" in data:
                widget.hover_color = self._parse_color(data["hover_color"])
            if "pressed_color" in data:
                widget.pressed_color = self._parse_color(data["pressed_color"])
            if "text_color" in data:
                widget.text_color = self._parse_color(data["text_color"])
            if "border_radius" in data:
                widget.border_radius = float(data["border_radius"])
            if "font_size" in data:
                widget.font_size = float(data["font_size"])
            if "padding" in data:
                widget.padding = float(data["padding"])

        # Checkbox attributes
        if isinstance(widget, Checkbox):
            if "text" in data:
                widget.text = data["text"]
            if "checked" in data:
                widget.checked = bool(data["checked"])
            if "box_color" in data:
                widget.box_color = self._parse_color(data["box_color"])
            if "check_color" in data:
                widget.check_color = self._parse_color(data["check_color"])
            if "hover_color" in data:
                widget.hover_color = self._parse_color(data["hover_color"])
            if "text_color" in data:
                widget.text_color = self._parse_color(data["text_color"])
            if "border_radius" in data:
                widget.border_radius = float(data["border_radius"])
            if "font_size" in data:
                widget.font_size = float(data["font_size"])
            if "box_size" in data:
                widget.box_size = float(data["box_size"])
            if "spacing" in data:
                widget.spacing = float(data["spacing"])

        # IconButton attributes
        if isinstance(widget, IconButton):
            if "icon" in data:
                widget.icon = data["icon"]
            if "tooltip" in data:
                widget.tooltip = data["tooltip"]
            if "background_color" in data:
                widget.background_color = self._parse_color(data["background_color"])
            if "hover_color" in data:
                widget.hover_color = self._parse_color(data["hover_color"])
            if "pressed_color" in data:
                widget.pressed_color = self._parse_color(data["pressed_color"])
            if "active_color" in data:
                widget.active_color = self._parse_color(data["active_color"])
            if "icon_color" in data:
                widget.icon_color = self._parse_color(data["icon_color"])
            if "border_radius" in data:
                widget.border_radius = float(data["border_radius"])
            if "size" in data:
                widget.size = float(data["size"])
            if "font_size" in data:
                widget.font_size = float(data["font_size"])
            if "active" in data:
                widget.active = bool(data["active"])

        # TextInput attributes
        if isinstance(widget, TextInput):
            if "text" in data:
                widget.text = str(data["text"])
            if "placeholder" in data:
                widget.placeholder = str(data["placeholder"])
            if "font_size" in data:
                widget.font_size = float(data["font_size"])
            if "padding" in data:
                widget.padding = float(data["padding"])
            if "background_color" in data:
                widget.background_color = self._parse_color(data["background_color"])
            if "focused_background_color" in data:
                widget.focused_background_color = self._parse_color(data["focused_background_color"])
            if "border_color" in data:
                widget.border_color = self._parse_color(data["border_color"])
            if "focused_border_color" in data:
                widget.focused_border_color = self._parse_color(data["focused_border_color"])
            if "text_color" in data:
                widget.text_color = self._parse_color(data["text_color"])
            if "placeholder_color" in data:
                widget.placeholder_color = self._parse_color(data["placeholder_color"])
            if "cursor_color" in data:
                widget.cursor_color = self._parse_color(data["cursor_color"])
            if "border_radius" in data:
                widget.border_radius = float(data["border_radius"])
            if "border_width" in data:
                widget.border_width = float(data["border_width"])

        # ProgressBar attributes
        if isinstance(widget, ProgressBar):
            if "value" in data:
                widget.value = float(data["value"])
            if "background_color" in data:
                widget.background_color = self._parse_color(data["background_color"])
            if "fill_color" in data:
                widget.fill_color = self._parse_color(data["fill_color"])
            if "border_radius" in data:
                widget.border_radius = float(data["border_radius"])
            if "show_text" in data:
                widget.show_text = bool(data["show_text"])
            if "text_color" in data:
                widget.text_color = self._parse_color(data["text_color"])
            if "font_size" in data:
                widget.font_size = float(data["font_size"])

        # Slider attributes
        if isinstance(widget, Slider):
            if "value" in data:
                widget.value = float(data["value"])
            if "min_value" in data:
                widget.min_value = float(data["min_value"])
            if "max_value" in data:
                widget.max_value = float(data["max_value"])
            if "step" in data:
                widget.step = float(data["step"])
            if "track_color" in data:
                widget.track_color = self._parse_color(data["track_color"])
            if "fill_color" in data:
                widget.fill_color = self._parse_color(data["fill_color"])
            if "thumb_color" in data:
                widget.thumb_color = self._parse_color(data["thumb_color"])
            if "thumb_hover_color" in data:
                widget.thumb_hover_color = self._parse_color(data["thumb_hover_color"])
            if "track_height" in data:
                widget.track_height = float(data["track_height"])
            if "thumb_radius" in data:
                widget.thumb_radius = float(data["thumb_radius"])
            if "border_radius" in data:
                widget.border_radius = float(data["border_radius"])

        # ComboBox attributes
        if isinstance(widget, ComboBox):
            if "items" in data:
                widget.items = list(data["items"])
            if "selected_index" in data:
                widget.selected_index = int(data["selected_index"])
            if "placeholder" in data:
                widget.placeholder = str(data["placeholder"])
            if "background_color" in data:
                widget.background_color = self._parse_color(data["background_color"])
            if "border_color" in data:
                widget.border_color = self._parse_color(data["border_color"])
            if "text_color" in data:
                widget.text_color = self._parse_color(data["text_color"])
            if "font_size" in data:
                widget.font_size = float(data["font_size"])
            if "border_radius" in data:
                widget.border_radius = float(data["border_radius"])

        # ImageWidget attributes
        if isinstance(widget, ImageWidget):
            if "image_path" in data:
                widget.image_path = str(data["image_path"])
            if "tint" in data:
                widget.tint = self._parse_color(data["tint"])

        # Separator attributes
        if isinstance(widget, Separator):
            if "orientation" in data:
                widget.orientation = data["orientation"]
            if "color" in data:
                widget.color = self._parse_color(data["color"])
            if "thickness" in data:
                widget.thickness = float(data["thickness"])
            if "margin" in data:
                widget.margin = float(data["margin"])

        # TreeNode attributes
        if isinstance(widget, TreeNode):
            if "expanded" in data:
                widget.expanded = bool(data["expanded"])
            # TreeNode children in YAML are subnodes, not Widget.children
            if "nodes" in data:
                for node_data in data["nodes"]:
                    child_node = self._parse_widget(node_data)
                    if isinstance(child_node, TreeNode):
                        widget.add_node(child_node)
            # "content" key creates a content widget
            if "content" in data:
                content_widget = self._parse_widget(data["content"])
                widget.content = content_widget

        # TreeWidget attributes
        if isinstance(widget, TreeWidget):
            if "indent_size" in data:
                widget.indent_size = float(data["indent_size"])
            if "toggle_size" in data:
                widget.toggle_size = float(data["toggle_size"])
            if "row_height" in data:
                widget.row_height = float(data["row_height"])
            if "row_spacing" in data:
                widget.row_spacing = float(data["row_spacing"])
            if "selected_background" in data:
                widget.selected_background = self._parse_color(data["selected_background"])
            if "hover_background" in data:
                widget.hover_background = self._parse_color(data["hover_background"])
            if "toggle_color" in data:
                widget.toggle_color = self._parse_color(data["toggle_color"])
            # TreeWidget children in YAML are root_nodes
            if "nodes" in data:
                for node_data in data["nodes"]:
                    child_node = self._parse_widget(node_data)
                    if isinstance(child_node, TreeNode):
                        widget.add_root(child_node)

        # TabBar attributes
        if isinstance(widget, TabBar):
            if "tabs" in data:
                widget.tabs = list(data["tabs"])
            if "selected_index" in data:
                widget.selected_index = int(data["selected_index"])
            if "tab_padding" in data:
                widget.tab_padding = float(data["tab_padding"])
            if "tab_spacing" in data:
                widget.tab_spacing = float(data["tab_spacing"])
            if "font_size" in data:
                widget.font_size = float(data["font_size"])
            if "tab_color" in data:
                widget.tab_color = self._parse_color(data["tab_color"])
            if "selected_tab_color" in data:
                widget.selected_tab_color = self._parse_color(data["selected_tab_color"])
            if "hover_tab_color" in data:
                widget.hover_tab_color = self._parse_color(data["hover_tab_color"])
            if "text_color" in data:
                widget.text_color = self._parse_color(data["text_color"])
            if "selected_text_color" in data:
                widget.selected_text_color = self._parse_color(data["selected_text_color"])
            if "indicator_color" in data:
                widget.indicator_color = self._parse_color(data["indicator_color"])
            if "indicator_height" in data:
                widget.indicator_height = float(data["indicator_height"])
            if "border_radius" in data:
                widget.border_radius = float(data["border_radius"])

        # TabView attributes
        if isinstance(widget, TabView):
            if "tab_position" in data:
                widget.tab_position = data["tab_position"]
            if "tabs" in data:
                # tabs: [{title: "Tab1", content: {type: ...}}, ...]
                for tab_data in data["tabs"]:
                    title = tab_data.get("title", "")
                    if "content" in tab_data:
                        content = self._parse_widget(tab_data["content"])
                        widget.add_tab(title, content)

        # Menu attributes
        if isinstance(widget, Menu):
            if "background_color" in data:
                widget.background_color = self._parse_color(data["background_color"])
            if "item_hover_color" in data:
                widget.item_hover_color = self._parse_color(data["item_hover_color"])
            if "text_color" in data:
                widget.text_color = self._parse_color(data["text_color"])
            if "shortcut_color" in data:
                widget.shortcut_color = self._parse_color(data["shortcut_color"])
            if "icon_color" in data:
                widget.icon_color = self._parse_color(data["icon_color"])
            if "separator_color" in data:
                widget.separator_color = self._parse_color(data["separator_color"])
            if "border_radius" in data:
                widget.border_radius = float(data["border_radius"])
            if "font_size" in data:
                widget.font_size = float(data["font_size"])
            if "item_height" in data:
                widget.item_height = float(data["item_height"])
            if "items" in data:
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
                widget.items = items

        # SpinBox attributes
        if isinstance(widget, SpinBox):
            if "value" in data:
                widget.value = float(data["value"])
            if "min_value" in data:
                widget.min_value = float(data["min_value"])
            if "max_value" in data:
                widget.max_value = float(data["max_value"])
            if "step" in data:
                widget.step = float(data["step"])
            if "decimals" in data:
                widget.decimals = int(data["decimals"])
            if "font_size" in data:
                widget.font_size = float(data["font_size"])
            if "padding" in data:
                widget.padding = float(data["padding"])
            if "button_width" in data:
                widget.button_width = float(data["button_width"])
            if "border_radius" in data:
                widget.border_radius = float(data["border_radius"])
            if "border_width" in data:
                widget.border_width = float(data["border_width"])

        # SliderEdit attributes
        if isinstance(widget, SliderEdit):
            if "value" in data:
                widget.value = float(data["value"])
            if "min_value" in data:
                widget.min_value = float(data["min_value"])
            if "max_value" in data:
                widget.max_value = float(data["max_value"])
            if "step" in data:
                widget.step = float(data["step"])
            if "decimals" in data:
                widget.decimals = int(data["decimals"])
            if "spacing" in data:
                widget.spacing = float(data["spacing"])
            if "spinbox_width" in data:
                widget.spinbox_width = float(data["spinbox_width"])

        # TextArea attributes
        if isinstance(widget, TextArea):
            if "text" in data:
                widget.text = str(data["text"])
            if "placeholder" in data:
                widget.placeholder = str(data["placeholder"])
            if "max_lines" in data:
                widget.max_lines = int(data["max_lines"])
            if "read_only" in data:
                widget.read_only = bool(data["read_only"])
            if "line_height" in data:
                widget.line_height = float(data["line_height"])
            if "font_size" in data:
                widget.font_size = float(data["font_size"])
            if "padding" in data:
                widget.padding = float(data["padding"])
            if "border_radius" in data:
                widget.border_radius = float(data["border_radius"])
            if "border_width" in data:
                widget.border_width = float(data["border_width"])
            if "show_scrollbar" in data:
                widget.show_scrollbar = bool(data["show_scrollbar"])
            if "scrollbar_width" in data:
                widget.scrollbar_width = float(data["scrollbar_width"])

        # MenuBar attributes
        if isinstance(widget, MenuBar):
            if "background_color" in data:
                widget.background_color = self._parse_color(data["background_color"])
            if "text_color" in data:
                widget.text_color = self._parse_color(data["text_color"])
            if "hover_color" in data:
                widget.hover_color = self._parse_color(data["hover_color"])
            if "active_color" in data:
                widget.active_color = self._parse_color(data["active_color"])
            if "font_size" in data:
                widget.font_size = float(data["font_size"])
            if "item_padding_x" in data:
                widget.item_padding_x = float(data["item_padding_x"])
            if "item_padding_y" in data:
                widget.item_padding_y = float(data["item_padding_y"])

        # ToolBar attributes
        if isinstance(widget, ToolBar):
            if "background_color" in data:
                widget.background_color = self._parse_color(data["background_color"])
            if "item_hover_color" in data:
                widget.item_hover_color = self._parse_color(data["item_hover_color"])
            if "icon_color" in data:
                widget.icon_color = self._parse_color(data["icon_color"])
            if "text_color" in data:
                widget.text_color = self._parse_color(data["text_color"])
            if "separator_color" in data:
                widget.separator_color = self._parse_color(data["separator_color"])
            if "border_radius" in data:
                widget.border_radius = float(data["border_radius"])
            if "font_size" in data:
                widget.font_size = float(data["font_size"])
            if "item_size" in data:
                widget.item_size = float(data["item_size"])

        # StatusBar attributes
        if isinstance(widget, StatusBar):
            if "text" in data:
                widget.set_text(str(data["text"]))
            if "background_color" in data:
                widget.background_color = self._parse_color(data["background_color"])
            if "text_color" in data:
                widget.text_color = self._parse_color(data["text_color"])
            if "temp_text_color" in data:
                widget.temp_text_color = self._parse_color(data["temp_text_color"])
            if "font_size" in data:
                widget.font_size = float(data["font_size"])
            if "padding_x" in data:
                widget.padding_x = float(data["padding_x"])

        # Dialog attributes
        if isinstance(widget, Dialog):
            if "title" in data:
                widget.title = str(data["title"])
            if "background_color" in data:
                widget.background_color = self._parse_color(data["background_color"])
            if "title_background_color" in data:
                widget.title_background_color = self._parse_color(data["title_background_color"])
            if "border_radius" in data:
                widget.border_radius = float(data["border_radius"])
            if "padding" in data:
                widget.padding = float(data["padding"])
            if "min_width" in data:
                widget.min_width = float(data["min_width"])

        # GroupBox attributes
        if isinstance(widget, GroupBox):
            if "title" in data:
                widget.title = str(data["title"])
            if "expanded" in data:
                widget.expanded = bool(data["expanded"])
            if "title_height" in data:
                widget.title_height = float(data["title_height"])
            if "content_padding" in data:
                widget.content_padding = float(data["content_padding"])
            if "title_padding" in data:
                widget.title_padding = float(data["title_padding"])
            if "font_size" in data:
                widget.font_size = float(data["font_size"])
            if "border_radius" in data:
                widget.border_radius = float(data["border_radius"])
            if "background_color" in data:
                widget.background_color = self._parse_color(data["background_color"])
            if "title_background_color" in data:
                widget.title_background_color = self._parse_color(data["title_background_color"])
            if "title_hover_color" in data:
                widget.title_hover_color = self._parse_color(data["title_hover_color"])
            if "title_text_color" in data:
                widget.title_text_color = self._parse_color(data["title_text_color"])
            if "arrow_color" in data:
                widget.arrow_color = self._parse_color(data["arrow_color"])
            if "border_color" in data:
                widget.border_color = self._parse_color(data["border_color"])

        # Canvas attributes
        if isinstance(widget, Canvas):
            if "background_color" in data:
                widget.background_color = self._parse_color(data["background_color"])
            if "min_zoom" in data:
                widget.min_zoom = float(data["min_zoom"])
            if "max_zoom" in data:
                widget.max_zoom = float(data["max_zoom"])
            if "zoom_factor" in data:
                widget.zoom_factor = float(data["zoom_factor"])

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
