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
        self._focused_widget: Widget | None = None

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

            anchor = self._root.anchor
            x, y = 0.0, 0.0

            if anchor == "absolute":
                # Absolute positioning using position_x/position_y
                if self._root.position_x is not None:
                    x = self._root.position_x.to_pixels(viewport_w)
                if self._root.position_y is not None:
                    y = self._root.position_y.to_pixels(viewport_h)
            else:
                # Calculate position based on anchor
                # Horizontal position
                if "left" in anchor:
                    x = 0
                elif "right" in anchor:
                    x = viewport_w - w
                else:  # center
                    x = (viewport_w - w) / 2

                # Vertical position
                if "top" in anchor:
                    y = 0
                elif "bottom" in anchor:
                    y = viewport_h - h
                else:  # center
                    y = (viewport_h - h) / 2

                # Apply offset
                x += self._root.offset_x
                y += self._root.offset_y

            self._root.layout(x, y, w, h, viewport_w, viewport_h)

    def render(self, viewport_w: int, viewport_h: int):
        """Render the UI."""
        if not self._root:
            return

        # Re-layout if viewport changed
        if viewport_w != self._viewport_w or viewport_h != self._viewport_h:
            self.layout(viewport_w, viewport_h)

        self._renderer.begin(viewport_w, viewport_h)
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

    def set_focus(self, widget: Widget | None):
        """Set the focused widget. Pass None to clear focus."""
        if self._focused_widget is widget:
            return
        if self._focused_widget is not None:
            self._focused_widget.on_blur()
        self._focused_widget = widget
        if self._focused_widget is not None:
            self._focused_widget.on_focus()

    def key_down(self, key: int, mods: int) -> bool:
        """Dispatch key down to the focused widget."""
        if self._focused_widget is not None:
            return self._focused_widget.on_key_down(key, mods)
        return False

    def text_input(self, text: str) -> bool:
        """Dispatch text input to the focused widget."""
        if self._focused_widget is not None:
            return self._focused_widget.on_text_input(text)
        return False

    def mouse_down(self, x: float, y: float) -> bool:
        """
        Handle mouse down event.

        Returns True if UI consumed the event.
        """
        if not self._root:
            return False

        hit = self._root.hit_test(x, y)

        # Focus management
        if hit is not None and hit.focusable:
            self.set_focus(hit)
        else:
            self.set_focus(None)

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
