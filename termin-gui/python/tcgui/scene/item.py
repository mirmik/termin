"""Graphics item primitives for scene-based interaction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tcgui.widgets.events import KeyEvent, MouseEvent, MouseWheelEvent, TextEvent
from tcgui.widgets.widget import Widget


@dataclass
class SceneTransform:
    """World-to-screen transform parameters."""

    origin_x: float
    origin_y: float
    zoom: float

    def world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        return (
            self.origin_x + wx * self.zoom,
            self.origin_y + wy * self.zoom,
        )


class GraphicsItem:
    """Base retained item for a lightweight scene graph."""

    def __init__(self) -> None:
        self.parent: GraphicsItem | None = None
        self.children: list[GraphicsItem] = []

        self.x: float = 0.0
        self.y: float = 0.0
        self.width: float = 100.0
        self.height: float = 60.0
        self.z_index: float = 0.0

        self.visible: bool = True
        self.enabled: bool = True
        self.selectable: bool = True
        self.draggable: bool = False
        self.selected: bool = False
        self.hovered: bool = False

        self.data: dict[str, Any] = {}

    def add_child(self, child: "GraphicsItem") -> "GraphicsItem":
        child.parent = self
        self.children.append(child)
        return child

    def remove_child(self, child: "GraphicsItem") -> None:
        if child in self.children:
            child.parent = None
            self.children.remove(child)

    def world_position(self) -> tuple[float, float]:
        if self.parent is None:
            return (self.x, self.y)
        px, py = self.parent.world_position()
        return (px + self.x, py + self.y)

    def world_bounds(self) -> tuple[float, float, float, float]:
        wx, wy = self.world_position()
        return (wx, wy, self.width, self.height)

    def contains_local(self, lx: float, ly: float) -> bool:
        return 0.0 <= lx <= self.width and 0.0 <= ly <= self.height

    def hit_test(self, wx: float, wy: float) -> "GraphicsItem | None":
        if not self.visible or not self.enabled:
            return None

        x, y = self.world_position()
        lx = wx - x
        ly = wy - y
        if not self.contains_local(lx, ly):
            return None

        for child in sorted(self.children, key=lambda i: i.z_index, reverse=True):
            hit = child.hit_test(wx, wy)
            if hit is not None:
                return hit
        return self

    def paint(self, renderer, transform: SceneTransform) -> None:
        """Draw item body. Override in subclasses."""
        del renderer, transform

    def render(self, renderer, transform: SceneTransform) -> None:
        if not self.visible:
            return
        self.paint(renderer, transform)
        for child in sorted(self.children, key=lambda i: i.z_index):
            child.render(renderer, transform)


class RectItem(GraphicsItem):
    """Simple rectangle item with optional text label."""

    def __init__(self, label: str = "") -> None:
        super().__init__()
        self.label = label
        self.fill_color = (0.22, 0.24, 0.30, 1.0)
        self.border_color = (0.36, 0.40, 0.50, 1.0)
        self.border_selected_color = (0.95, 0.72, 0.20, 1.0)
        self.text_color = (0.90, 0.92, 0.96, 1.0)
        self.font_size = 13.0
        self.border_width = 1.0

    def paint(self, renderer, transform: SceneTransform) -> None:
        wx, wy, ww, wh = self.world_bounds()
        sx, sy = transform.world_to_screen(wx, wy)
        sw = ww * transform.zoom
        sh = wh * transform.zoom

        renderer.draw_rect(sx, sy, sw, sh, self.fill_color)
        border = self.border_selected_color if self.selected else self.border_color
        renderer.draw_rect_outline(sx, sy, sw, sh, border, self.border_width)

        if self.label:
            renderer.draw_text(
                sx + 8.0,
                sy + min(sh - 6.0, self.font_size + 8.0),
                self.label,
                self.text_color,
                self.font_size,
            )


class GraphicsWidgetItem(GraphicsItem):
    """Scene item that hosts a regular Widget and dispatches input to it."""

    def __init__(self, widget: Widget) -> None:
        super().__init__()
        self.widget = widget
        self.selectable = False
        self.draggable = False
        self._hovered_widget: Widget | None = None
        self._pressed_widget: Widget | None = None
        self._focused_widget: Widget | None = None

    def _screen_rect(self, transform: SceneTransform) -> tuple[float, float, float, float]:
        wx, wy, ww, wh = self.world_bounds()
        sx, sy = transform.world_to_screen(wx, wy)
        sw = ww * transform.zoom
        sh = wh * transform.zoom
        return sx, sy, sw, sh

    def _set_ui_recursive(self, widget: Widget, ui) -> None:
        widget._ui = ui
        for child in widget.children:
            self._set_ui_recursive(child, ui)

    def ensure_ui(self, ui) -> None:
        if ui is None:
            return
        if self.widget._ui is ui:
            return
        self._set_ui_recursive(self.widget, ui)

    def layout_widget(self, transform: SceneTransform, viewport_w: float, viewport_h: float, ui=None) -> None:
        self.ensure_ui(ui)
        sx, sy, sw, sh = self._screen_rect(transform)
        self.widget.layout(sx, sy, max(1.0, sw), max(1.0, sh), viewport_w, viewport_h)

    def paint(self, renderer, transform: SceneTransform) -> None:
        # Render the hosted widget in screen space at transformed item bounds.
        _, _, sw, sh = self._screen_rect(transform)
        self.layout_widget(transform, max(1.0, sw), max(1.0, sh))
        self.widget.render(renderer)

    def clear_interaction_state(self) -> None:
        self.clear_hover_state()
        self.clear_focus_state()

    def clear_hover_state(self) -> None:
        if self._hovered_widget is not None:
            self._hovered_widget.on_mouse_leave()
        self._hovered_widget = None
        self._pressed_widget = None

    def clear_focus_state(self) -> None:
        if self._focused_widget is not None:
            self._focused_widget.on_blur()
        self._focused_widget = None

    def _update_hover(self, hit: Widget | None, event: MouseEvent) -> None:
        if hit is not self._hovered_widget:
            if self._hovered_widget is not None:
                self._hovered_widget.on_mouse_leave()
            if hit is not None:
                hit.on_mouse_enter()
            self._hovered_widget = hit
        if hit is not None:
            hit.on_mouse_move(event)

    def dispatch_mouse_move(self, x: float, y: float, mods: int = 0) -> bool:
        event = MouseEvent(x, y, mods=mods)
        if self._pressed_widget is not None:
            self._pressed_widget.on_mouse_move(event)
            return True
        hit = self.widget.hit_test(x, y)
        self._update_hover(hit, event)
        return hit is not None

    def dispatch_mouse_down(self, x: float, y: float, button, mods: int = 0) -> bool:
        event = MouseEvent(x, y, button=button, mods=mods)
        hit = self.widget.hit_test(x, y)
        self._update_hover(hit, event)
        if hit is None:
            return False
        if hit.focusable and self._focused_widget is not hit:
            if self._focused_widget is not None:
                self._focused_widget.on_blur()
            self._focused_widget = hit
            self._focused_widget.on_focus()
        if hit.on_mouse_down(event):
            self._pressed_widget = hit
            return True
        return False

    def dispatch_mouse_up(self, x: float, y: float, button, mods: int = 0) -> bool:
        if self._pressed_widget is None:
            return False
        event = MouseEvent(x, y, button=button, mods=mods)
        self._pressed_widget.on_mouse_up(event)
        self._pressed_widget = None
        return True

    def dispatch_mouse_wheel(self, dx: float, dy: float, x: float, y: float) -> bool:
        event = MouseWheelEvent(dx, dy, x, y)
        hit = self.widget.hit_test(x, y)
        widget = hit
        while widget is not None:
            if widget.on_mouse_wheel(event):
                return True
            widget = widget.parent
        return hit is not None

    def dispatch_key_down(self, key, mods: int = 0) -> bool:
        if self._focused_widget is None:
            return False
        return self._focused_widget.on_key_down(KeyEvent(key, mods))

    def dispatch_text_input(self, text: str) -> bool:
        if self._focused_widget is None:
            return False
        return self._focused_widget.on_text_input(TextEvent(text))
