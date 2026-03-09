"""Button widget."""

from __future__ import annotations
from typing import Callable

from tcgui.widgets.widget import Widget
from tcgui.widgets.events import MouseEvent
from tcgui.widgets.theme import current_theme as _t


class Button(Widget):
    """Clickable button widget."""

    def __init__(self):
        super().__init__()
        self.text: str = ""
        self.icon: str | None = None

        # Colors
        self.background_color: tuple[float, float, float, float] = _t.bg_surface
        self.hover_color: tuple[float, float, float, float] = _t.hover
        self.pressed_color: tuple[float, float, float, float] = _t.pressed
        self.text_color: tuple[float, float, float, float] = _t.text_primary
        self.border_radius: float = _t.border_radius

        # Toggle mode
        self.checkable: bool = False
        self.checked: bool = False
        self.checked_color: tuple[float, float, float, float] = _t.accent

        # State
        self.hovered: bool = False
        self.pressed: bool = False

        # Callback
        self.on_click: Callable[[], None] | None = None

        # Text settings
        self.font_size: float = _t.font_size
        self.padding: float = 10

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h)
            )
        # Size based on text + padding
        text_width = len(self.text) * self.font_size * 0.6
        return (text_width + self.padding * 2, self.font_size + self.padding * 2)

    def render(self, renderer: 'UIRenderer'):
        # Choose color based on state
        if self.pressed:
            color = self.pressed_color
        elif self.hovered:
            color = self.hover_color
        elif self.checkable and self.checked:
            color = self.checked_color
        else:
            color = self.background_color

        # Draw background
        renderer.draw_rect(
            self.x, self.y, self.width, self.height,
            color, self.border_radius
        )

        # Draw text centered
        if self.text:
            renderer.draw_text_centered(
                self.x + self.width / 2,
                self.y + self.height / 2,
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
        if not self.enabled:
            return False
        self.pressed = True
        return True

    def on_mouse_up(self, event: MouseEvent):
        if self.pressed and self.contains(event.x, event.y):
            if self.checkable:
                self.checked = not self.checked
            if self.on_click:
                self.on_click()
        self.pressed = False
