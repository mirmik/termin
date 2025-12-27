"""Widget-based UI system with YAML layout support."""

from termin.visualization.ui.widgets.units import Value, Unit, px, ndc, pct
from termin.visualization.ui.widgets.widget import Widget
from termin.visualization.ui.widgets.containers import HStack, VStack, Panel
from termin.visualization.ui.widgets.basic import Label, Button, Checkbox, IconButton, Separator
from termin.visualization.ui.widgets.renderer import UIRenderer
from termin.visualization.ui.widgets.loader import UILoader
from termin.visualization.ui.widgets.ui import UI
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
    # Rendering
    "UIRenderer",
    # Loading
    "UILoader",
    # Main class
    "UI",
    # Component
    "UIComponent",
]
