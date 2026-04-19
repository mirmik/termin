"""UIComponent — Component that holds and manages a widget-based UI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.core.component import InputComponent
from termin.visualization.core.input_events import MouseButtonEvent, MouseMoveEvent
from tcbase import Action
from tcgui.widgets.ui import UI
from tcgui.widgets.widget import Widget
from tgfx.font import FontTextureAtlas
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
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
        from tcgui.widgets import Panel, Button, VStack

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
        self._ui_handle: UIHandle | None = None
        self._ui_layout_name: str = ""
        # Viewport dimensions for input handling before first render
        self._viewport_w: int = 0
        self._viewport_h: int = 0
        # Widget tree staged before the first render() — UI itself can
        # only exist once we've been handed a live Tgfx2Context, but
        # callers (scene deserialisation, editor inspector) want to
        # load layouts and look up widgets long before that. Kept here
        # and flushed onto self._ui in render() once graphics arrives.
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
        """Root widget of the UI tree. Before the first render (when UI
        itself still doesn't exist) returns the pending root instead."""
        if self._ui is not None:
            return self._ui.root
        return self._pending_root

    @root.setter
    def root(self, widget: Widget | None):
        """Set the root widget. Stored on the UI if it already exists,
        otherwise staged until the first render() call builds the UI."""
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
        from termin.assets.ui_handle import UIHandle

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
        from termin.assets.ui_handle import UIHandle

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
        """Load UI layout from a YAML file.

        UILoader builds the widget tree without needing a live UI, so
        this works before the first render() — the resulting root is
        staged on self._pending_root and handed to UI when graphics
        arrives. If UI is already live, the root goes straight in.
        """
        from tcgui.widgets.loader import UILoader
        loader = UILoader()
        widget = loader.load(path)
        self.root = widget
        return widget

    def load_string(self, yaml_str: str) -> Widget:
        """Load UI layout from a YAML string. See load() for the timing
        story — same deal, just a different source."""
        from tcgui.widgets.loader import UILoader
        loader = UILoader()
        widget = loader.load_string(yaml_str)
        self.root = widget
        return widget

    def _walk_tree(self, root: Widget):
        """Generator yielding every widget in the subtree rooted at
        ``root``. Used for pre-render find()/find_all() when UI itself
        does not exist yet."""
        if root is None:
            return
        yield root
        children = getattr(root, "children", None) or []
        for child in children:
            yield from self._walk_tree(child)

    def find(self, name: str) -> Widget | None:
        """Find a widget by name. Works both after the first render
        (via UI.find) and before (manual tree walk over pending root)."""
        if self._ui is not None:
            return self._ui.find(name)
        for w in self._walk_tree(self._pending_root):
            if getattr(w, "name", None) == name:
                return w
        return None

    def find_all(self, name: str) -> list[Widget]:
        """Find all widgets with a given name. Same timing story as
        find() — pre-render walks the staged tree manually."""
        if self._ui is not None:
            return self._ui.find_all(name)
        return [w for w in self._walk_tree(self._pending_root)
                if getattr(w, "name", None) == name]

    def render(self, viewport_w: int, viewport_h: int,
               ctx2=None, target_tex2=None):
        """Render the UI through the framegraph ctx2.

        Called by UIWidgetPass. UI is composited offscreen and the
        resulting tgfx2 texture is blitted into ``target_tex2``. The UI
        itself is built lazily on the first call — until then there's
        no Tgfx2Context to give it, so we stash the layout in
        _pending_root and construct UI here once ctx2 arrives.
        """
        if ctx2 is None or target_tex2 is None:
            # No host-provided ctx ⇒ we have no way to draw (UI needs
            # graphics). Scene-only UIComponent without a rendering
            # path is a no-op.
            return

        if self._ui is None:
            # First render — build Tgfx2Context over the framegraph's
            # ctx2 (same device as every other renderer; keeps
            # TextureHandles in the same HandlePool so the blit below
            # resolves them), then create the UI with it and flush any
            # pre-render layout into place.
            from tgfx._tgfx_native import Tgfx2Context
            self._graphics = Tgfx2Context.from_context(ctx2)
            self._ui = UI(self._graphics, font=self._font)
            if self._pending_root is not None:
                self._ui.root = self._pending_root
                self._pending_root = None

        if self._ui.root is None:
            return

        tex = self._ui.render_compose(viewport_w, viewport_h)
        if tex is not None:
            ctx2.blit(tex, target_tex2)

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
        # Input lands before render() may have built the live UI —
        # drop it silently; once the first render() flushes the pending
        # layout into place subsequent events go through.
        if self._ui is None or self._ui.root is None:
            return

        # Get viewport dimensions from event
        vp = event.viewport
        if vp is not None:
            px, py, pw, ph = vp.pixel_rect
            self._viewport_w = pw
            self._viewport_h = ph

        if event.action == Action.PRESS.value:
            self.mouse_down(event.x, event.y)
        elif event.action == Action.RELEASE.value:
            self.mouse_up(event.x, event.y)

    def on_mouse_move(self, event: MouseMoveEvent):
        """Handle mouse move events from the input system."""
        # Input lands before render() may have built the live UI —
        # drop it silently; once the first render() flushes the pending
        # layout into place subsequent events go through.
        if self._ui is None or self._ui.root is None:
            return

        # Get viewport dimensions from event
        vp = event.viewport
        if vp is not None:
            px, py, pw, ph = vp.pixel_rect
            self._viewport_w = pw
            self._viewport_h = ph

        self.mouse_move(event.x, event.y)
