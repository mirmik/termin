"""Label widget."""

from __future__ import annotations

from tcgui.widgets.widget import Widget
from tcgui.widgets.theme import current_theme as _t


class Label(Widget):
    """Text label widget."""

    def __init__(self):
        super().__init__()
        self.text: str = ""
        self._text_color: tuple[float, float, float, float] = _t.text_primary
        self.font_size: float = _t.font_size
        self.alignment: str = "left"  # left, center, right
        self.mouse_transparent = True

    @property
    def color(self) -> tuple[float, float, float, float]:
        return self._text_color

    @color.setter
    def color(self, value: tuple[float, float, float, float]) -> None:
        self._text_color = value

    @property
    def text_color(self) -> tuple[float, float, float, float]:
        return self._text_color

    @text_color.setter
    def text_color(self, value: tuple[float, float, float, float]) -> None:
        self._text_color = value

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        # Approximate text size (will be refined when we have font metrics)
        text_width = len(self.text) * self.font_size * 0.6
        text_height = self.font_size * 1.2
        if self.preferred_width:
            text_width = self.preferred_width.to_pixels(viewport_w)
        if self.preferred_height:
            text_height = self.preferred_height.to_pixels(viewport_h)
        return (text_width, text_height)

    def render(self, renderer: 'UIRenderer'):
        text = self._fit_text(renderer)
        renderer.begin_clip(self.x, self.y, self.width, self.height)
        if self.alignment == "center":
            renderer.draw_text_centered(
                self.x + self.width / 2,
                self.y + self.height / 2,
                text,
                self.text_color,
                self.font_size
            )
        elif self.alignment == "right":
            text_width, _ = renderer.measure_text(text, self.font_size)
            renderer.draw_text(
                self.x + max(0.0, self.width - text_width),
                self.y + self.font_size,
                text,
                self.text_color,
                self.font_size
            )
        else:  # left
            renderer.draw_text(
                self.x,
                self.y + self.font_size,
                text,
                self.text_color,
                self.font_size
            )
        renderer.end_clip()

    def _fit_text(self, renderer: 'UIRenderer') -> str:
        if self.width <= 0:
            return ""

        text_width, _ = renderer.measure_text(self.text, self.font_size)
        if text_width <= self.width:
            return self.text

        ellipsis = "..."
        ellipsis_width, _ = renderer.measure_text(ellipsis, self.font_size)
        if ellipsis_width > self.width:
            return ""

        lo = 0
        hi = len(self.text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            candidate = self.text[:mid] + ellipsis
            candidate_width, _ = renderer.measure_text(candidate, self.font_size)
            if candidate_width <= self.width:
                lo = mid
            else:
                hi = mid - 1
        return self.text[:lo] + ellipsis
