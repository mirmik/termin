"""UIComponent — Component that holds and manages a widget-based UI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.core.component import InputComponent
from termin.visualization.core.input_events import MouseButtonEvent, MouseMoveEvent
from termin.visualization.platform.backends.base import Action
from termin.visualization.ui.widgets.ui import UI
from termin.visualization.ui.widgets.widget import Widget
from termin.visualization.ui.font import FontTextureAtlas
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend
    from termin.assets.ui_handle import UIHandle


class UIComponent(InputComponent):
    """
    Component that manages a widget-based UI overlay.

    The UI is rendered after the 3D scene as an overlay.
    Multiple UIComponents can exist in a scene, rendered by priority.

    Usage:
        # Create entity with UI
        ui_entity = Entity(name="ui")
        ui_comp = UIComponent()
        ui_entity.add_component(ui_comp)
        scene.add(ui_entity)

        # Load UI from YAML
        ui_comp.load("ui/main_menu.yaml")

        # Or build programmatically
        from termin.visualization.ui.widgets import Panel, Button, VStack

        panel = Panel()
        panel.padding = 10
        stack = VStack()
        stack.spacing = 5
        btn = Button()
        btn.text = "Click me"
        btn.on_click = lambda: print("Clicked!")
        stack.add_child(btn)
        panel.add_child(stack)
        ui_comp.root = panel

        # Find widgets by name
        button = ui_comp.find("my_button")

    Attributes:
        priority: Render order (lower = rendered first, appears behind).
        font: Font atlas for text rendering.
    """

    inspect_fields = {
        "ui_layout": InspectField(
            path="ui_layout",
            label="UI Layout",
            kind="ui_handle",
            setter=lambda obj, val: obj.set_ui_layout(val),
        ),
    }

    def __init__(self, priority: int = 0):
        super().__init__(enabled=True, active_in_editor=False)
        self._ui: UI | None = None
        self._font: FontTextureAtlas | None = None
        self._priority = priority
        self._graphics: GraphicsBackend | None = None
        self._ui_handle: UIHandle | None = None
        self._ui_layout_name: str = ""
        # Viewport dimensions for input handling before first render
        self._viewport_w: int = 0
        self._viewport_h: int = 0

    @property
    def priority(self) -> int:
        """Render priority (lower renders first)."""
        return self._priority

    @priority.setter
    def priority(self, value: int):
        self._priority = value

    @property
    def ui(self) -> UI | None:
        """The underlying UI manager."""
        return self._ui

    @property
    def root(self) -> Widget | None:
        """Root widget of the UI tree."""
        if self._ui is None:
            return None
        return self._ui.root

    @root.setter
    def root(self, widget: Widget | None):
        """Set the root widget."""
        self._ensure_ui()
        self._ui.root = widget

    @property
    def font(self) -> FontTextureAtlas | None:
        """Font atlas for text rendering."""
        return self._font

    @font.setter
    def font(self, value: FontTextureAtlas | None):
        self._font = value
        if self._ui is not None:
            self._ui.font = value

    @property
    def ui_layout(self) -> "UIHandle | None":
        """UI layout handle."""
        return self._ui_handle

    @ui_layout.setter
    def ui_layout(self, value: "UIHandle | None"):
        """Set UI layout from handle."""
        self.set_ui_layout(value)

    def set_ui_layout(self, handle: "UIHandle | None") -> None:
        """Set UI layout from handle."""
        from termin.assets.ui_handle import UIHandle

        if handle is None:
            self._ui_handle = None
            self._ui_layout_name = ""
            self._ensure_ui()
            self._ui.root = None
            return

        self._ui_handle = handle
        asset = handle.get_asset()
        if asset is not None:
            self._ui_layout_name = asset.name
            widget = handle.widget
            if widget is not None:
                self._ensure_ui()
                self._ui.root = widget
        else:
            self._ui_layout_name = ""

    def set_ui_layout_by_name(self, name: str) -> None:
        """Set UI layout by name from ResourceManager."""
        from termin.assets.ui_handle import UIHandle

        if name:
            self._ui_handle = UIHandle.from_name(name)
            self._ui_layout_name = name
            widget = self._ui_handle.widget
            if widget is not None:
                self._ensure_ui()
                self._ui.root = widget
        else:
            self._ui_handle = None
            self._ui_layout_name = ""
            if self._ui is not None:
                self._ui.root = None

    def _ensure_ui(self):
        """Lazily create UI when graphics backend is available."""
        if self._ui is not None:
            return

        if self._graphics is None:
            from termin.visualization.platform.backends import get_default_graphics_backend
            self._graphics = get_default_graphics_backend()

        self._ui = UI(self._graphics, self._font)

    def load(self, path: str) -> Widget:
        """
        Load UI layout from a YAML file.

        Args:
            path: Path to YAML file.

        Returns:
            The root widget.
        """
        self._ensure_ui()
        return self._ui.load(path)

    def load_string(self, yaml_str: str) -> Widget:
        """
        Load UI layout from a YAML string.

        Args:
            yaml_str: YAML content.

        Returns:
            The root widget.
        """
        self._ensure_ui()
        return self._ui.load_string(yaml_str)

    def find(self, name: str) -> Widget | None:
        """
        Find a widget by name.

        Args:
            name: Widget name to search for.

        Returns:
            Widget or None if not found.
        """
        if self._ui is None:
            return None
        return self._ui.find(name)

    def find_all(self, name: str) -> list[Widget]:
        """
        Find all widgets with a given name.

        Args:
            name: Widget name to search for.

        Returns:
            List of matching widgets.
        """
        if self._ui is None:
            return []
        return self._ui.find_all(name)

    def render(self, graphics: GraphicsBackend, viewport_w: int, viewport_h: int,
               context_key: int | None = None):
        """
        Render the UI.

        Called by UIWidgetPass during the render pipeline.

        Args:
            graphics: Graphics backend.
            viewport_w: Viewport width in pixels.
            viewport_h: Viewport height in pixels.
            context_key: Context key for GPU resource management.
        """
        if self._graphics is None:
            self._graphics = graphics

        self._ensure_ui()

        if self._ui.root is None:
            return

        self._ui.render(viewport_w, viewport_h, context_key)

    def _ensure_layout(self):
        """Ensure layout is up to date for input handling."""
        if self._ui is None or self._ui.root is None:
            return
        if self._viewport_w > 0 and self._viewport_h > 0:
            self._ui.layout(self._viewport_w, self._viewport_h)

    def mouse_move(self, x: float, y: float) -> bool:
        """
        Handle mouse move event.

        Args:
            x, y: Mouse position in pixels.

        Returns:
            True if UI consumed the event.
        """
        if self._ui is None:
            return False
        self._ensure_layout()
        return self._ui.mouse_move(x, y)

    def mouse_down(self, x: float, y: float) -> bool:
        """
        Handle mouse down event.

        Args:
            x, y: Mouse position in pixels.

        Returns:
            True if UI consumed the event.
        """
        if self._ui is None:
            return False
        self._ensure_layout()
        return self._ui.mouse_down(x, y)

    def mouse_up(self, x: float, y: float) -> bool:
        """
        Handle mouse up event.

        Args:
            x, y: Mouse position in pixels.

        Returns:
            True if UI consumed the event.
        """
        if self._ui is None:
            return False
        self._ensure_layout()
        return self._ui.mouse_up(x, y)

    # --- InputComponent interface ---

    def on_mouse_button(self, event: MouseButtonEvent):
        """Handle mouse button events from the input system."""
        self._ensure_ui()
        if self._ui is None or self._ui.root is None:
            return

        # Get viewport dimensions from event
        vp = event.viewport
        if vp is not None:
            px, py, pw, ph = vp.pixel_rect
            self._viewport_w = pw
            self._viewport_h = ph

        if event.action == Action.PRESS:
            self.mouse_down(event.x, event.y)
        elif event.action == Action.RELEASE:
            self.mouse_up(event.x, event.y)

    def on_mouse_move(self, event: MouseMoveEvent):
        """Handle mouse move events from the input system."""
        self._ensure_ui()
        if self._ui is None or self._ui.root is None:
            return

        # Get viewport dimensions from event
        vp = event.viewport
        if vp is not None:
            px, py, pw, ph = vp.pixel_rect
            self._viewport_w = pw
            self._viewport_h = ph

        self.mouse_move(event.x, event.y)
