"""Transparent anchored stacking container."""

from __future__ import annotations

from tcgui.widgets.panel import Panel


class Overlay(Panel):
    """Lay out every child independently by its anchor and declaration order."""

    def __init__(self):
        super().__init__()
        self.background_color = (0.0, 0.0, 0.0, 0.0)

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h),
            )
        sizes = [
            child.compute_size(viewport_w, viewport_h) for child in self.children
        ]
        return (
            max((width for width, _height in sizes), default=0.0),
            max((height for _width, height in sizes), default=0.0),
        )
