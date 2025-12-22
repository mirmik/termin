"""Main UI class that manages the widget tree."""

from __future__ import annotations

from termin.visualization.platform.backends.base import GraphicsBackend
from termin.visualization.ui.font import FontTextureAtlas
from termin.visualization.ui.widgets.widget import Widget
from termin.visualization.ui.widgets.renderer import UIRenderer
from termin.visualization.ui.widgets.loader import UILoader


class UI:
    """
    Main UI manager class.

    Manages a widget tree, handles input, and renders the UI.
    """

    def __init__(self, graphics: GraphicsBackend, font: FontTextureAtlas | None = None):
        self._graphics = graphics
        self._renderer = UIRenderer(graphics, font)
        self._loader = UILoader()

        self._root: Widget | None = None
        self._hovered_widget: Widget | None = None
        self._pressed_widget: Widget | None = None

        # Viewport dimensions
        self._viewport_w: int = 0
        self._viewport_h: int = 0

    @property
    def root(self) -> Widget | None:
        return self._root

    @root.setter
    def root(self, widget: Widget | None):
        self._root = widget

    @property
    def font(self) -> FontTextureAtlas | None:
        return self._renderer.font

    @font.setter
    def font(self, value: FontTextureAtlas | None):
        self._renderer.font = value

    @property
    def loader(self) -> UILoader:
        """Access to the loader for registering custom widget types."""
        return self._loader

    def load(self, path: str) -> Widget:
        """Load UI from a YAML file and set as root."""
        self._root = self._loader.load(path)
        return self._root

    def load_string(self, yaml_str: str) -> Widget:
        """Load UI from a YAML string and set as root."""
        self._root = self._loader.load_string(yaml_str)
        return self._root

    def find(self, name: str) -> Widget | None:
        """Find a widget by name."""
        if self._root:
            return self._root.find(name)
        return None

    def find_all(self, name: str) -> list[Widget]:
        """Find all widgets with the given name."""
        if self._root:
            return self._root.find_all(name)
        return []

    def layout(self, viewport_w: int, viewport_h: int):
        """Perform layout calculation."""
        self._viewport_w = viewport_w
        self._viewport_h = viewport_h

        if self._root:
            w, h = self._root.compute_size(viewport_w, viewport_h)
            # Position at top-left by default
            self._root.layout(0, 0, w, h, viewport_w, viewport_h)

    def render(self, viewport_w: int, viewport_h: int, context_key: int | None = None):
        """Render the UI."""
        if not self._root:
            return

        # Re-layout if viewport changed
        if viewport_w != self._viewport_w or viewport_h != self._viewport_h:
            self.layout(viewport_w, viewport_h)

        self._renderer.begin(viewport_w, viewport_h, context_key)
        self._root.render(self._renderer)
        self._renderer.end()

    def mouse_move(self, x: float, y: float) -> bool:
        """
        Handle mouse move event.

        Returns True if UI consumed the event (e.g., dragging).
        """
        if not self._root:
            return False

        # If we're dragging, send move to pressed widget
        if self._pressed_widget:
            self._pressed_widget.on_mouse_move(x, y)
            return True

        # Otherwise, update hover state
        hit = self._root.hit_test(x, y)

        if hit != self._hovered_widget:
            if self._hovered_widget:
                self._hovered_widget.on_mouse_leave()
            if hit:
                hit.on_mouse_enter()
            self._hovered_widget = hit

        return False

    def mouse_down(self, x: float, y: float) -> bool:
        """
        Handle mouse down event.

        Returns True if UI consumed the event.
        """
        if not self._root:
            return False

        hit = self._root.hit_test(x, y)
        if hit:
            if hit.on_mouse_down(x, y):
                self._pressed_widget = hit
                return True

        return False

    def mouse_up(self, x: float, y: float) -> bool:
        """
        Handle mouse up event.

        Returns True if UI consumed the event.
        """
        if self._pressed_widget:
            self._pressed_widget.on_mouse_up(x, y)
            self._pressed_widget = None
            return True

        return False
