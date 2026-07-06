"""UIComponent - Component that holds and manages a widget-based UI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tcbase import Action
from tcgui.widgets.ui import UI
from tcgui.widgets.widget import Widget
from tgfx.font import FontTextureAtlas
from termin.input import InputComponent, MouseButtonEvent, MouseMoveEvent
from termin.inspect import InspectField

if TYPE_CHECKING:
    from termin.default_assets.ui.handle import UIHandle


class UIComponent(InputComponent):
    """
    Component that manages a widget-based UI overlay.

    The UI is rendered after the 3D scene as an overlay.
    Multiple UIComponents can exist in a scene, rendered by priority.
    """

    input_category = "overlay"

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
        self._ui_handle: UIHandle | None = None
        self._ui_layout_name: str = ""
        self._viewport_w: int = 0
        self._viewport_h: int = 0
        self._pending_root: Widget | None = None
        self._graphics = None

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
        if self._ui is not None:
            return self._ui.root
        return self._pending_root

    @root.setter
    def root(self, widget: Widget | None):
        if self._ui is not None:
            self._ui.root = widget
        else:
            self._pending_root = widget

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
        if handle is None:
            self._ui_handle = None
            self._ui_layout_name = ""
            self.root = None
            return

        self._ui_handle = handle
        asset = handle.get_asset()
        if asset is not None:
            self._ui_layout_name = asset.name
            widget = handle.widget
            if widget is not None:
                self.root = widget
        else:
            self._ui_layout_name = ""

    def set_ui_layout_by_name(self, name: str) -> None:
        """Set UI layout by name from ResourceManager."""
        from termin.default_assets.ui.handle import UIHandle

        if name:
            self._ui_handle = UIHandle.from_name(name)
            self._ui_layout_name = name
            widget = self._ui_handle.widget
            if widget is not None:
                self.root = widget
        else:
            self._ui_handle = None
            self._ui_layout_name = ""
            self.root = None

    def load(self, path: str) -> Widget:
        """Load UI layout from a YAML file."""
        from tcgui.widgets.loader import UILoader

        loader = UILoader()
        widget = loader.load(path)
        self.root = widget
        return widget

    def load_string(self, yaml_str: str) -> Widget:
        """Load UI layout from a YAML string."""
        from tcgui.widgets.loader import UILoader

        loader = UILoader()
        widget = loader.load_string(yaml_str)
        self.root = widget
        return widget

    def _walk_tree(self, root: Widget):
        if root is None:
            return
        yield root
        children = root.children
        for child in children:
            yield from self._walk_tree(child)

    def find(self, name: str) -> Widget | None:
        if self._ui is not None:
            return self._ui.find(name)
        for widget in self._walk_tree(self._pending_root):
            if widget.name == name:
                return widget
        return None

    def find_all(self, name: str) -> list[Widget]:
        if self._ui is not None:
            return self._ui.find_all(name)
        return [
            widget
            for widget in self._walk_tree(self._pending_root)
            if widget.name == name
        ]

    def render(self, viewport_w: int, viewport_h: int, ctx2=None, target_tex2=None):
        """Render the UI through the framegraph ctx2."""
        if ctx2 is None or target_tex2 is None:
            return

        if self._ui is None:
            from tgfx._tgfx_native import Tgfx2Context

            self._graphics = Tgfx2Context.from_context(ctx2)
            self._ui = UI(self._graphics, font=self._font)
            if self._pending_root is not None:
                self._ui.root = self._pending_root
                self._pending_root = None

        if self._ui.root is None:
            return

        self._ui.render_compose(viewport_w, viewport_h, target_color=target_tex2)

    def _ensure_layout(self):
        """Ensure layout is up to date for input handling."""
        if self._ui is None or self._ui.root is None:
            return
        if self._viewport_w > 0 and self._viewport_h > 0:
            self._ui.layout(self._viewport_w, self._viewport_h)

    def mouse_move(self, x: float, y: float) -> bool:
        if self._ui is None:
            return False
        self._ensure_layout()
        return self._ui.mouse_move(x, y)

    def mouse_down(self, x: float, y: float) -> bool:
        if self._ui is None:
            return False
        self._ensure_layout()
        return self._ui.mouse_down(x, y)

    def mouse_up(self, x: float, y: float) -> bool:
        if self._ui is None:
            return False
        self._ensure_layout()
        return self._ui.mouse_up(x, y)

    def on_mouse_button(self, event: MouseButtonEvent):
        """Handle mouse button events from the input system."""
        if self._ui is None or self._ui.root is None:
            return

        vp = event.viewport
        if vp is not None:
            px, py, pw, ph = vp.pixel_rect
            self._viewport_w = pw
            self._viewport_h = ph

        if event.action == Action.PRESS.value:
            event.handled = event.handled or self.mouse_down(event.x, event.y)
        elif event.action == Action.RELEASE.value:
            event.handled = event.handled or self.mouse_up(event.x, event.y)

    def on_mouse_move(self, event: MouseMoveEvent):
        """Handle mouse move events from the input system."""
        if self._ui is None or self._ui.root is None:
            return

        vp = event.viewport
        if vp is not None:
            px, py, pw, ph = vp.pixel_rect
            self._viewport_w = pw
            self._viewport_h = ph

        event.handled = event.handled or self.mouse_move(event.x, event.y)
