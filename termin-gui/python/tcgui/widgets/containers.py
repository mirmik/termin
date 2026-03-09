"""Container widgets — re-export hub for backward compatibility."""

from tcgui.widgets.hstack import HStack
from tcgui.widgets.vstack import VStack
from tcgui.widgets.grid_layout import GridLayout
from tcgui.widgets.panel import Panel
from tcgui.widgets.scroll_area import ScrollArea
from tcgui.widgets.group_box import GroupBox

__all__ = [
    "HStack", "VStack", "GridLayout", "Panel", "ScrollArea", "GroupBox",
]
