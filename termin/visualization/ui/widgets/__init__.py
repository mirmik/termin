"""Widget-based UI system with YAML layout support."""

from tcgui.widgets.units import Value, Unit, px, ndc, pct
from tcgui.widgets.widget import Widget
from tcgui.widgets.containers import HStack, VStack, Panel
from tcgui.widgets.basic import Label, Button, Checkbox, IconButton, Separator, ImageWidget, TextInput, ListWidget
from tcgui.widgets.renderer import UIRenderer
from tcgui.widgets.loader import UILoader
from tcgui.widgets.ui import UI
from termin.visualization.ui.widgets.component import UIComponent

__all__ = [
    # Units
    "Value",
    "Unit",
    "px",
    "ndc",
    "pct",
    # Base
    "Widget",
    # Containers
    "HStack",
    "VStack",
    "Panel",
    # Basic widgets
    "Label",
    "Button",
    "Checkbox",
    "IconButton",
    "Separator",
    "ImageWidget",
    "TextInput",
    "ListWidget",
    # Rendering
    "UIRenderer",
    # Loading
    "UILoader",
    # Main class
    "UI",
    # Component
    "UIComponent",
]
