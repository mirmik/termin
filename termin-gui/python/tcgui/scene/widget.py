"""Scene view widget with pan/zoom/selection/drag support."""

from __future__ import annotations

from tcbase import Key, MouseButton

from tcgui.scene.item import GraphicsItem, GraphicsWidgetItem, SceneTransform
from tcgui.scene.scene import GraphicsScene
from tcgui.widgets.events import MouseEvent, MouseWheelEvent, KeyEvent, TextEvent
from tcgui.widgets.widget import Widget


class SceneView(Widget):
    """Widget that displays a GraphicsScene."""

    def __init__(self, scene: GraphicsScene | None = None) -> None:
        super().__init__()
        self.focusable = True
        self.cursor = "move"

        self.scene = scene if scene is not None else GraphicsScene()

        self.background_color = (0.10, 0.11, 0.13, 1.0)
        self.grid_color = (0.17, 0.19, 0.24, 1.0)
        self.grid_axis_color = (0.30, 0.33, 0.42, 1.0)
        self.show_grid = True
        self.grid_step = 40.0

        self.zoom = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 4.0
        self.zoom_factor = 1.15
        self.offset_x = 0.0
        self.offset_y = 0.0

        self._panning = False
        self._pan_start_x = 0.0
        self._pan_start_y = 0.0
        self._pan_start_offset_x = 0.0
        self._pan_start_offset_y = 0.0

        self._drag_item: GraphicsItem | None = None
        self._drag_item_start_x = 0.0
        self._drag_item_start_y = 0.0
        self._drag_mouse_start_wx = 0.0
        self._drag_mouse_start_wy = 0.0
        self._widget_hover_item: GraphicsWidgetItem | None = None
        self._widget_focus_item: GraphicsWidgetItem | None = None
        self._widget_pressed_item: GraphicsWidgetItem | None = None

    def world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        return (
            self.x + self.offset_x + wx * self.zoom,
            self.y + self.offset_y + wy * self.zoom,
        )

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        return (
            (sx - self.x - self.offset_x) / self.zoom,
            (sy - self.y - self.offset_y) / self.zoom,
        )

    def _make_transform(self) -> SceneTransform:
        return SceneTransform(
            origin_x=self.x + self.offset_x,
            origin_y=self.y + self.offset_y,
            zoom=self.zoom,
        )

    def _draw_grid(self, renderer) -> None:
        if not self.show_grid or self.grid_step <= 0.0:
            return

        world_left, world_top = self.screen_to_world(self.x, self.y)
        world_right, world_bottom = self.screen_to_world(
            self.x + self.width, self.y + self.height
        )

        step = self.grid_step
        start_x = int(world_left // step) * step
        end_x = int(world_right // step + 1) * step
        start_y = int(world_top // step) * step
        end_y = int(world_bottom // step + 1) * step

        for wx in range(int(start_x), int(end_x) + 1, int(step)):
            sx, _ = self.world_to_screen(float(wx), 0.0)
            color = self.grid_axis_color if wx == 0 else self.grid_color
            renderer.draw_line(sx, self.y, sx, self.y + self.height, color, 1.0)

        for wy in range(int(start_y), int(end_y) + 1, int(step)):
            _, sy = self.world_to_screen(0.0, float(wy))
            color = self.grid_axis_color if wy == 0 else self.grid_color
            renderer.draw_line(self.x, sy, self.x + self.width, sy, color, 1.0)

    def render(self, renderer) -> None:
        renderer.draw_rect(self.x, self.y, self.width, self.height, self.background_color)
        renderer.begin_clip(self.x, self.y, self.width, self.height)
        self._draw_grid(renderer)
        self.scene.render(renderer, self._make_transform())
        renderer.end_clip()

    def _selectable_ancestor(self, item: GraphicsItem | None) -> GraphicsItem | None:
        current = item
        while current is not None and not current.selectable:
            current = current.parent
        return current

    def _draggable_ancestor(self, item: GraphicsItem | None) -> GraphicsItem | None:
        current = item
        while current is not None and not current.draggable:
            current = current.parent
        return current

    def _set_widget_focus_item(self, item: GraphicsWidgetItem | None) -> None:
        if self._widget_focus_item is item:
            return
        if self._widget_focus_item is not None:
            self._widget_focus_item.clear_focus_state()
        self._widget_focus_item = item

    def _prepare_widget_item_layout(self, item: GraphicsWidgetItem) -> None:
        item.layout_widget(self._make_transform(), self.width, self.height, self._ui)

    def _clear_widget_hover(self) -> None:
        if self._widget_hover_item is None:
            return
        self._widget_hover_item.clear_hover_state()
        self._widget_hover_item = None

    def on_mouse_down(self, event: MouseEvent) -> bool:
        if event.button == MouseButton.MIDDLE:
            self._panning = True
            self._pan_start_x = event.x
            self._pan_start_y = event.y
            self._pan_start_offset_x = self.offset_x
            self._pan_start_offset_y = self.offset_y
            return True

        if event.button != MouseButton.LEFT:
            return False

        wx, wy = self.screen_to_world(event.x, event.y)
        hit = self.scene.hit_test(wx, wy)
        if isinstance(hit, GraphicsWidgetItem):
            self._prepare_widget_item_layout(hit)
            self.scene.set_selected(self._selectable_ancestor(hit.parent))
            self._set_widget_focus_item(hit)
            handled = hit.dispatch_mouse_down(event.x, event.y, event.button, event.mods)
            if handled:
                self._widget_pressed_item = hit
                self._widget_hover_item = hit
                return True
            return True

        self._clear_widget_hover()
        self.scene.set_selected(self._selectable_ancestor(hit))
        self._set_widget_focus_item(None)

        drag_target = self._draggable_ancestor(hit)
        if drag_target is not None:
            self._drag_item = drag_target
            self._drag_item_start_x = drag_target.x
            self._drag_item_start_y = drag_target.y
            self._drag_mouse_start_wx = wx
            self._drag_mouse_start_wy = wy
        return True

    def on_mouse_move(self, event: MouseEvent) -> None:
        if self._panning:
            self.offset_x = self._pan_start_offset_x + (event.x - self._pan_start_x)
            self.offset_y = self._pan_start_offset_y + (event.y - self._pan_start_y)
            return

        if self._widget_pressed_item is not None:
            self._prepare_widget_item_layout(self._widget_pressed_item)
            self._widget_pressed_item.dispatch_mouse_move(event.x, event.y)
            return

        wx, wy = self.screen_to_world(event.x, event.y)
        hit = self.scene.hit_test(wx, wy)
        if isinstance(hit, GraphicsWidgetItem):
            self._prepare_widget_item_layout(hit)
            if self._widget_hover_item is not hit:
                self._clear_widget_hover()
                self._widget_hover_item = hit
            hit.dispatch_mouse_move(event.x, event.y)
            return
        self._clear_widget_hover()

        if self._drag_item is not None:
            self._drag_item.x = self._drag_item_start_x + (wx - self._drag_mouse_start_wx)
            self._drag_item.y = self._drag_item_start_y + (wy - self._drag_mouse_start_wy)

    def on_mouse_up(self, event: MouseEvent) -> None:
        if self._widget_pressed_item is not None:
            self._prepare_widget_item_layout(self._widget_pressed_item)
            self._widget_pressed_item.dispatch_mouse_up(event.x, event.y, event.button, event.mods)
            self._widget_pressed_item = None
        self._panning = False
        self._drag_item = None

    def on_mouse_wheel(self, event: MouseWheelEvent) -> bool:
        wx, wy = self.screen_to_world(event.x, event.y)
        hit = self.scene.hit_test(wx, wy)
        if isinstance(hit, GraphicsWidgetItem):
            self._prepare_widget_item_layout(hit)
            if hit.dispatch_mouse_wheel(event.dx, event.dy, event.x, event.y):
                return True

        before_wx, before_wy = self.screen_to_world(event.x, event.y)
        factor = self.zoom_factor if event.dy > 0 else 1.0 / self.zoom_factor
        self.zoom = max(self.min_zoom, min(self.zoom * factor, self.max_zoom))
        self.offset_x = (event.x - self.x) - before_wx * self.zoom
        self.offset_y = (event.y - self.y) - before_wy * self.zoom
        return True

    def on_key_down(self, event: KeyEvent) -> bool:
        if self._widget_focus_item is not None:
            self._prepare_widget_item_layout(self._widget_focus_item)
            if self._widget_focus_item.dispatch_key_down(event.key, event.mods):
                return True
        if event.key == Key.DELETE:
            for item in self.scene.selected_items[:]:
                if item.parent is None:
                    self.scene.remove_item(item)
            self.scene.clear_selection()
            return True
        return False

    def on_text_input(self, event: TextEvent) -> bool:
        if self._widget_focus_item is None:
            return False
        self._prepare_widget_item_layout(self._widget_focus_item)
        return self._widget_focus_item.dispatch_text_input(event.text)
