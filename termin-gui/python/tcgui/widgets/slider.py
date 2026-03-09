"""Slider widget."""

from __future__ import annotations
from typing import Callable

from tcgui.widgets.widget import Widget
from tcgui.widgets.events import MouseEvent
from tcgui.widgets.theme import current_theme as _t


class Slider(Widget):
    """Slider widget for selecting a numeric value from a range."""

    def __init__(self):
        super().__init__()
        self.value: float = 0.0
        self.min_value: float = 0.0
        self.max_value: float = 1.0
        self.step: float = 0.0  # 0 = continuous

        self.track_color: tuple[float, float, float, float] = _t.bg_surface
        self.fill_color: tuple[float, float, float, float] = _t.accent
        self.thumb_color: tuple[float, float, float, float] = _t.text_secondary
        self.thumb_hover_color: tuple[float, float, float, float] = _t.text_primary
        self.track_height: float = 4.0
        self.thumb_radius: float = 8.0
        self.border_radius: float = 2.0

        # State
        self._dragging: bool = False
        self.hovered: bool = False

        # Callback
        self.on_changed: Callable[[float], None] | None = None

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h),
            )
        w = self.preferred_width.to_pixels(viewport_w) if self.preferred_width else 200
        h = self.preferred_height.to_pixels(viewport_h) if self.preferred_height else self.thumb_radius * 2
        return (w, h)

    def _value_to_x(self) -> float:
        """Convert current value to x position of thumb center."""
        rng = self.max_value - self.min_value
        if rng <= 0:
            return self.x + self.thumb_radius
        ratio = (self.value - self.min_value) / rng
        track_start = self.x + self.thumb_radius
        track_end = self.x + self.width - self.thumb_radius
        return track_start + ratio * (track_end - track_start)

    def _x_to_value(self, x: float) -> float:
        """Convert x position to value."""
        track_start = self.x + self.thumb_radius
        track_end = self.x + self.width - self.thumb_radius
        track_len = track_end - track_start
        if track_len <= 0:
            return self.min_value
        ratio = (x - track_start) / track_len
        ratio = max(0.0, min(1.0, ratio))
        val = self.min_value + ratio * (self.max_value - self.min_value)
        if self.step > 0:
            val = round((val - self.min_value) / self.step) * self.step + self.min_value
        return max(self.min_value, min(self.max_value, val))

    def render(self, renderer: 'UIRenderer'):
        cy = self.y + self.height / 2
        track_y = cy - self.track_height / 2

        # Track background
        renderer.draw_rect(
            self.x + self.thumb_radius, track_y,
            self.width - self.thumb_radius * 2, self.track_height,
            self.track_color, self.border_radius
        )

        # Fill up to thumb
        thumb_x = self._value_to_x()
        fill_w = thumb_x - (self.x + self.thumb_radius)
        if fill_w > 0:
            renderer.draw_rect(
                self.x + self.thumb_radius, track_y,
                fill_w, self.track_height,
                self.fill_color, self.border_radius
            )

        # Thumb
        tc = self.thumb_hover_color if (self.hovered or self._dragging) else self.thumb_color
        renderer.draw_rect(
            thumb_x - self.thumb_radius, cy - self.thumb_radius,
            self.thumb_radius * 2, self.thumb_radius * 2,
            tc, self.thumb_radius
        )

    def on_mouse_enter(self):
        self.hovered = True

    def on_mouse_leave(self):
        self.hovered = False

    def on_mouse_down(self, event: MouseEvent) -> bool:
        self._dragging = True
        self._set_value_from_x(event.x)
        return True

    def on_mouse_move(self, event: MouseEvent):
        if self._dragging:
            self._set_value_from_x(event.x)

    def on_mouse_up(self, event: MouseEvent):
        self._dragging = False

    def _set_value_from_x(self, x: float):
        new_val = self._x_to_value(x)
        if new_val != self.value:
            self.value = new_val
            if self.on_changed:
                self.on_changed(self.value)
