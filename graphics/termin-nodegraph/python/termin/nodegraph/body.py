"""Body widgets and logical layout shared by the nodegraph views."""

from collections.abc import Callable
from dataclasses import dataclass

from termin.gui_native import TcDocument, WidgetRef
from termin.nodegraph.model import Node


@dataclass(frozen=True)
class NodeBodyLayout:
    """Layout requested for a node body widget in graph world units."""

    height: float
    inset_left: float = 8.0
    inset_right: float = 8.0
    inset_top: float = 8.0
    inset_bottom: float = 8.0
    gap_before: float = 7.0


@dataclass(frozen=True)
class NodeBodyContent:
    """A native widget whose lifetime is transferred to the graph view."""

    widget: WidgetRef
    layout: NodeBodyLayout
    update: Callable[[Node], None] | None = None


NodeBodyContentProvider = Callable[[TcDocument, Node], NodeBodyContent | None]
