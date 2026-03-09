"""IconButton widget."""

from __future__ import annotations
from typing import Callable

from tcgui.widgets.widget import Widget
from tcgui.widgets.events import MouseEvent
from tcgui.widgets.theme import current_theme as _t


class IconButton(Widget):
    """Compact square button with icon/symbol."""

    def __init__(self):
        super().__init__()
        self.icon: str = ""  # Single character or short text as icon
        self.tooltip: str = ""

        # Colors
        _bg = _t.bg_surface
        self.background_color: tuple[float, float, float, float] = (_bg[0], _bg[1], _bg[2], 0.9)
        self.hover_color: tuple[float, float, float, float] = _t.hover
        self.pressed_color: tuple[float, float, float, float] = _t.pressed
        self.active_color: tuple[float, float, float, float] = _t.accent
        self.icon_color: tuple[float, float, float, float] = _t.text_secondary
        self.border_radius: float = _t.border_radius + 1

        # State
        self.hovered: bool = False
        self.pressed: bool = False
        self.active: bool = False  # Toggle state for mode buttons

        # Callback
        self.on_click: Callable[[], None] | None = None

        # Size
        self.size: float = 28
        self.font_size: float = 16

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h)
            )
        return (self.size, self.size)

    def render(self, renderer: 'UIRenderer'):
        # Choose color based on state
        if self.pressed:
            color = self.pressed_color
        elif self.active:
            color = self.active_color
        elif self.hovered:
            color = self.hover_color
        else:
            color = self.background_color

        # Draw background
        renderer.draw_rect(
            self.x, self.y, self.width, self.height,
            color, self.border_radius
        )

        # Draw icon centered
        if self.icon:
            renderer.draw_text_centered(
                self.x + self.width / 2,
                self.y + self.height / 2,
                self.icon,
                self.icon_color,
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
            if self.on_click:
                self.on_click()
        self.pressed = False
