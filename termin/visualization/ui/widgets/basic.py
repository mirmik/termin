"""Basic widgets: Label, Button, Separator."""

from __future__ import annotations
from typing import Callable

from termin.visualization.ui.widgets.widget import Widget


class Label(Widget):
    """Text label widget."""

    def __init__(self):
        super().__init__()
        self.text: str = ""
        self.color: tuple[float, float, float, float] = (1, 1, 1, 1)
        self.font_size: float = 14
        self.alignment: str = "left"  # left, center, right

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h)
            )
        # Approximate text size (will be refined when we have font metrics)
        text_width = len(self.text) * self.font_size * 0.6
        text_height = self.font_size * 1.2
        return (text_width, text_height)

    def render(self, renderer: 'UIRenderer'):
        if self.alignment == "center":
            renderer.draw_text_centered(
                self.x + self.width / 2,
                self.y + self.height / 2,
                self.text,
                self.color,
                self.font_size
            )
        elif self.alignment == "right":
            text_width, _ = renderer.measure_text(self.text, self.font_size)
            renderer.draw_text(
                self.x + self.width - text_width,
                self.y + self.font_size,
                self.text,
                self.color,
                self.font_size
            )
        else:  # left
            renderer.draw_text(
                self.x,
                self.y + self.font_size,
                self.text,
                self.color,
                self.font_size
            )


class Button(Widget):
    """Clickable button widget."""

    def __init__(self):
        super().__init__()
        self.text: str = ""
        self.icon: str | None = None

        # Colors
        self.background_color: tuple[float, float, float, float] = (0.3, 0.3, 0.3, 1.0)
        self.hover_color: tuple[float, float, float, float] = (0.4, 0.4, 0.4, 1.0)
        self.pressed_color: tuple[float, float, float, float] = (0.2, 0.2, 0.2, 1.0)
        self.text_color: tuple[float, float, float, float] = (1, 1, 1, 1)
        self.border_radius: float = 3

        # State
        self.hovered: bool = False
        self.pressed: bool = False

        # Callback
        self.on_click: Callable[[], None] | None = None

        # Text settings
        self.font_size: float = 14
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

    def on_mouse_down(self, x: float, y: float) -> bool:
        self.pressed = True
        return True

    def on_mouse_up(self, x: float, y: float):
        if self.pressed and self.contains(x, y):
            if self.on_click:
                self.on_click()
        self.pressed = False


class Separator(Widget):
    """Visual separator line."""

    def __init__(self):
        super().__init__()
        self.orientation: str = "vertical"  # vertical, horizontal
        self.color: tuple[float, float, float, float] = (0.5, 0.5, 0.5, 1.0)
        self.thickness: float = 1
        self.margin: float = 4  # space around separator

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.orientation == "vertical":
            return (self.thickness + self.margin * 2, 0)  # height from parent
        else:
            return (0, self.thickness + self.margin * 2)  # width from parent

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float):
        # Separator takes full extent in the stacking direction
        if self.orientation == "vertical":
            actual_width = self.thickness + self.margin * 2
            super().layout(x, y, actual_width, height, viewport_w, viewport_h)
        else:
            actual_height = self.thickness + self.margin * 2
            super().layout(x, y, width, actual_height, viewport_w, viewport_h)

    def render(self, renderer: 'UIRenderer'):
        if self.orientation == "vertical":
            lx = self.x + self.margin + self.thickness / 2
            renderer.draw_rect(
                lx - self.thickness / 2,
                self.y + self.margin,
                self.thickness,
                self.height - self.margin * 2,
                self.color
            )
        else:
            ly = self.y + self.margin + self.thickness / 2
            renderer.draw_rect(
                self.x + self.margin,
                ly - self.thickness / 2,
                self.width - self.margin * 2,
                self.thickness,
                self.color
            )
