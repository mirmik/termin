"""YAML loader for the widget-based UI system."""

from __future__ import annotations

from typing import Type
import yaml

from termin.visualization.ui.widgets.widget import Widget
from termin.visualization.ui.widgets.containers import HStack, VStack, Panel
from termin.visualization.ui.widgets.basic import Label, Button, Checkbox, IconButton, Separator, ImageWidget, TextInput
from termin.visualization.ui.widgets.units import Value


class UILoader:
    """Loads UI widget trees from YAML files."""

    # Registry of widget types
    WIDGET_TYPES: dict[str, Type[Widget]] = {
        "HStack": HStack,
        "VStack": VStack,
        "Panel": Panel,
        "Label": Label,
        "Button": Button,
        "Checkbox": Checkbox,
        "IconButton": IconButton,
        "Separator": Separator,
        "Image": ImageWidget,
        "TextInput": TextInput,
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
