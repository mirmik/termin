"""Checkbox widget."""

from __future__ import annotations
from typing import Callable

from tcgui.widgets.widget import Widget
from tcgui.widgets.events import MouseEvent
from tcgui.widgets.theme import current_theme as _t


class Checkbox(Widget):
    """Toggle checkbox widget with visual indicator."""

    def __init__(self):
        super().__init__()
        self.text: str = ""
        self.checked: bool = False

        # Colors
        self.box_color: tuple[float, float, float, float] = _t.bg_surface
        self.check_color: tuple[float, float, float, float] = _t.accent_success
        self.hover_color: tuple[float, float, float, float] = _t.hover
        self.text_color: tuple[float, float, float, float] = _t.text_primary
        self.border_radius: float = _t.border_radius

        # State
        self.hovered: bool = False
        self.pressed: bool = False

        # Callback
        self.on_changed: Callable[[bool], None] | None = None

        # Text settings
        self.font_size: float = _t.font_size
        self.box_size: float = 18
        self.spacing: float = _t.spacing

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h)
            )
        # Size based on box + text
        text_width = len(self.text) * self.font_size * 0.6 if self.text else 0
        total_width = self.box_size + (self.spacing + text_width if self.text else 0)
        return (total_width, max(self.box_size, self.font_size))

    def render(self, renderer: 'UIRenderer'):
        # Box background color based on state
        if self.hovered:
            box_bg = self.hover_color
        else:
            box_bg = self.box_color

        # Draw checkbox box
        box_y = self.y + (self.height - self.box_size) / 2
        renderer.draw_rect(
            self.x, box_y, self.box_size, self.box_size,
            box_bg, self.border_radius
        )

        # Draw checkmark if checked
        if self.checked:
            # Inner filled rectangle as checkmark indicator
            inset = 4
            renderer.draw_rect(
                self.x + inset, box_y + inset,
                self.box_size - inset * 2, self.box_size - inset * 2,
                self.check_color, self.border_radius - 1
            )

        # Draw text label
        if self.text:
            text_x = self.x + self.box_size + self.spacing
            renderer.draw_text(
                text_x,
                self.y + self.height / 2 + self.font_size / 3,
                self.text,
                self.text_color,
                self.font_size
            )

    def on_mouse_enter(self):
        self.hovered = True

    def on_mouse_leave(self):
        self.hovered = False
        self.pressed = False

    def on_mouse_down(self, event: MouseEvent) -> bool:
        self.pressed = True
        return True

    def on_mouse_up(self, event: MouseEvent):
        if self.pressed and self.contains(event.x, event.y):
            self.checked = not self.checked
            if self.on_changed:
                self.on_changed(self.checked)
        self.pressed = False
