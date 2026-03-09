"""ProgressBar widget."""

from __future__ import annotations

from tcgui.widgets.widget import Widget
from tcgui.widgets.theme import current_theme as _t


class ProgressBar(Widget):
    """Progress bar widget displaying a value between 0.0 and 1.0."""

    def __init__(self):
        super().__init__()
        self.value: float = 0.0
        self.background_color: tuple[float, float, float, float] = _t.bg_surface
        self.fill_color: tuple[float, float, float, float] = _t.accent
        self.border_radius: float = _t.border_radius
        self.show_text: bool = False
        self.text_color: tuple[float, float, float, float] = _t.text_primary
        self.font_size: float = _t.font_size_small + 1

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h),
            )
        w = self.preferred_width.to_pixels(viewport_w) if self.preferred_width else 200
        h = self.preferred_height.to_pixels(viewport_h) if self.preferred_height else 20
        return (w, h)

    def render(self, renderer: 'UIRenderer'):
        # Background
        renderer.draw_rect(
            self.x, self.y, self.width, self.height,
            self.background_color, self.border_radius
        )

        # Fill
        clamped = max(0.0, min(1.0, self.value))
        fill_w = self.width * clamped
        if fill_w > 0:
            renderer.draw_rect(
                self.x, self.y, fill_w, self.height,
                self.fill_color, self.border_radius
            )

        # Optional percentage text
        if self.show_text:
            text = f"{int(clamped * 100)}%"
            renderer.draw_text_centered(
                self.x + self.width / 2,
                self.y + self.height / 2,
                text, self.text_color, self.font_size
            )
