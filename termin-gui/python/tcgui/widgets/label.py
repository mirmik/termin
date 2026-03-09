"""Label widget."""

from __future__ import annotations

from tcgui.widgets.widget import Widget
from tcgui.widgets.theme import current_theme as _t


class Label(Widget):
    """Text label widget."""

    def __init__(self):
        super().__init__()
        self.text: str = ""
        self.color: tuple[float, float, float, float] = _t.text_primary
        self.font_size: float = _t.font_size
        self.alignment: str = "left"  # left, center, right
        self.mouse_transparent = True

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
