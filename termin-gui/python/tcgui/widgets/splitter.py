"""Draggable splitter between panels in HStack/VStack."""

from __future__ import annotations

from tcgui.widgets.widget import Widget
from tcgui.widgets.events import MouseEvent
from tcgui.widgets.units import px
from tcgui.widgets.theme import current_theme as _t


class Splitter(Widget):
    """Splitter bar. Drag to resize the panel on the given side.

    Horizontal (for HStack)::

        splitter = Splitter(target=left_panel, side="right")
        hstack.add_child(left_panel)
        hstack.add_child(splitter)
        hstack.add_child(canvas)

    Vertical (for VStack)::

        splitter = Splitter(target=bottom_panel, side="top")
        vstack.add_child(main_area)
        vstack.add_child(splitter)
        vstack.add_child(bottom_panel)
    """

    def __init__(self, target: Widget, side: str = "left"):
        super().__init__()
        self._target = target
        self._side = side  # "left", "right", "top", "bottom"
        self._vertical = side in ("top", "bottom")
        self.cursor = "move"

        if self._vertical:
            self.preferred_height = px(5)
        else:
            self.preferred_width = px(5)

        self.color: tuple[float, float, float, float] = _t.text_muted
        self.hover_color: tuple[float, float, float, float] = _t.accent
        self.bar_width: float = 1.0

        self._dragging = False
        self._drag_start: float = 0
        self._drag_start_size: float = 0
        self._hovered = False
        self._min_size: float = 50
        self._max_size: float = 800

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self._vertical:
            h = self.preferred_height.to_pixels(viewport_h) if self.preferred_height else 5
            return (0, h)
        else:
            w = self.preferred_width.to_pixels(viewport_w) if self.preferred_width else 5
            return (w, 0)

    def render(self, renderer):
        c = self.hover_color if (self._hovered or self._dragging) else self.color
        if self._vertical:
            cy = self.y + self.height / 2 - self.bar_width / 2
            renderer.draw_rect(self.x, cy, self.width, self.bar_width, c)
        else:
            cx = self.x + self.width / 2 - self.bar_width / 2
            renderer.draw_rect(cx, self.y, self.bar_width, self.height, c)

    def hit_test(self, px: float, py: float) -> Widget | None:
        if not self.visible:
            return None
        if not self.contains(px, py):
            return None
        return self

    def on_mouse_move(self, event: MouseEvent):
        if self._dragging:
            if self._vertical:
                delta = event.y - self._drag_start
                # side="top": splitter is above target → drag down = target shrinks
                # side="bottom": splitter is below target → drag down = target grows
                if self._side == "top":
                    delta = -delta
                new_size = max(self._min_size, min(self._max_size, self._drag_start_size + delta))
                self._target.preferred_height = px(new_size)
            else:
                delta = event.x - self._drag_start
                # side="left": splitter is left of target → drag right = target shrinks
                # side="right": splitter is right of target → drag right = target grows
                if self._side == "left":
                    delta = -delta
                new_size = max(self._min_size, min(self._max_size, self._drag_start_size + delta))
                self._target.preferred_width = px(new_size)
            if self._ui:
                self._ui.request_layout()
        else:
            self._hovered = True

    def on_mouse_leave(self):
        self._hovered = False

    def on_mouse_down(self, event: MouseEvent) -> bool:
        self._dragging = True
        if self._vertical:
            self._drag_start = event.y
            th = self._target.preferred_height
            self._drag_start_size = th.to_pixels(1000) if th else self._target.height
        else:
            self._drag_start = event.x
            tw = self._target.preferred_width
            self._drag_start_size = tw.to_pixels(1000) if tw else self._target.width
        return True

    def on_mouse_up(self, event: MouseEvent):
        self._dragging = False
