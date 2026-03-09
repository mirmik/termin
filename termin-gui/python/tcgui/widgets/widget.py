"""Base widget class for the UI system."""

from __future__ import annotations
from typing import Callable

from tcgui.widgets.units import Value, px
from tcgui.widgets.events import MouseEvent, MouseWheelEvent, KeyEvent, TextEvent


class Widget:
    """Base class for all UI widgets."""

    def __init__(self):
        self.name: str | None = None
        self.parent: Widget | None = None
        self.children: list[Widget] = []

        # Size preference (can be px or ndc)
        self.preferred_width: Value | None = None
        self.preferred_height: Value | None = None

        # Position anchor: where to position the widget
        # Options: "top-left", "top-center", "top-right",
        #          "center-left", "center", "center-right",
        #          "bottom-left", "bottom-center", "bottom-right"
        #          "absolute" - use position_x/position_y directly
        self.anchor: str = "top-left"

        # Offset from anchor position (in pixels)
        self.offset_x: float = 0
        self.offset_y: float = 0

        # Absolute position (used when anchor="absolute")
        # Can be px, ndc, or %
        self.position_x: Value | None = None
        self.position_y: Value | None = None

        # Computed layout (always in pixels after layout pass)
        self.x: float = 0
        self.y: float = 0
        self.width: float = 0
        self.height: float = 0

        # State
        self.visible: bool = True
        self.enabled: bool = True
        self.focusable: bool = False

        # Tooltip text (shown on hover after delay)
        self.tooltip: str | None = None

        # Layout stretch: when True, widget fills remaining space in HStack/VStack
        self.stretch: bool = False

        # Clip children rendering to widget bounds
        self.clip: bool = False

        # When True, hit_test skips this widget (events pass through to parent)
        self.mouse_transparent: bool = False

        # Cursor: "", "arrow", "cross", "hand", "text", "move"
        self.cursor: str = ""

        # Context menu (shown on right-click)
        self.context_menu = None  # Menu | None (avoid circular import)

        # Back-reference to UI (set automatically when attached to UI tree)
        self._ui = None  # UI | None

    def add_child(self, child: Widget) -> Widget:
        """Add a child widget."""
        child.parent = self
        self.children.append(child)
        # Propagate _ui reference if we're already in a UI tree
        if self._ui is not None:
            self._ui._set_ui_recursive(child)
        return child

    def remove_child(self, child: Widget):
        """Remove a child widget."""
        if child in self.children:
            child.parent = None
            self.children.remove(child)

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        """
        Compute preferred size in pixels.
        Override in subclasses for custom sizing logic.
        """
        w = self.preferred_width.to_pixels(viewport_w) if self.preferred_width else 0
        h = self.preferred_height.to_pixels(viewport_h) if self.preferred_height else 0
        return (w, h)

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float):
        """
        Position this widget and layout children.
        Coordinates are in pixels.
        """
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def render(self, renderer: 'UIRenderer'):
        """Render this widget. Override in subclasses."""
        if self.clip:
            renderer.begin_clip(self.x, self.y, self.width, self.height)
        for child in self.children:
            if child.visible:
                child.render(renderer)
        if self.clip:
            renderer.end_clip()

    def contains(self, px: float, py: float) -> bool:
        """Check if point (in pixels) is inside this widget."""
        return (self.x <= px < self.x + self.width and
                self.y <= py < self.y + self.height)

    def hit_test(self, px: float, py: float) -> Widget | None:
        """Find the topmost widget at the given pixel coordinates."""
        if not self.visible:
            return None
        if not self.contains(px, py):
            return None

        # Check children in reverse order (topmost first)
        for child in reversed(self.children):
            hit = child.hit_test(px, py)
            if hit:
                return hit

        if self.mouse_transparent:
            return None

        return self

    def find(self, name: str) -> Widget | None:
        """Find a widget by name in this subtree."""
        if self.name == name:
            return self
        for child in self.children:
            found = child.find(name)
            if found:
                return found
        return None

    def find_all(self, name: str) -> list[Widget]:
        """Find all widgets with the given name."""
        result = []
        if self.name == name:
            result.append(self)
        for child in self.children:
            result.extend(child.find_all(name))
        return result

    # Mouse events (override in interactive widgets)
    def on_mouse_enter(self):
        pass

    def on_mouse_leave(self):
        pass

    def on_mouse_down(self, event: MouseEvent) -> bool:
        """Handle mouse button down. Return True if handled."""
        return False

    def on_mouse_move(self, event: MouseEvent):
        """Handle mouse move (or drag)."""
        pass

    def on_mouse_up(self, event: MouseEvent):
        """Handle mouse button up."""
        pass

    def on_mouse_wheel(self, event: MouseWheelEvent) -> bool:
        """Handle mouse wheel. event.dy > 0 = scroll up. Return True if handled."""
        return False

    # Focus events (override in focusable widgets)
    def on_focus(self):
        pass

    def on_blur(self):
        pass

    # Keyboard events (override in focusable widgets)
    def on_key_down(self, event: KeyEvent) -> bool:
        """Handle key down. Return True if handled."""
        return False

    def on_text_input(self, event: TextEvent) -> bool:
        """Handle text input. Return True if handled."""
        return False
