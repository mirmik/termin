"""Panel container."""

from __future__ import annotations

from tcgui.widgets.widget import Widget
from tcgui.widgets.theme import current_theme as _t


class Panel(Widget):
    """Container with background and padding."""

    def __init__(self):
        super().__init__()
        self.padding: float = 0  # pixels
        _bg = _t.bg_surface
        self.background_color: tuple[float, float, float, float] = (_bg[0], _bg[1], _bg[2], 0.9)
        self.border_radius: float = 0
        self.background_image: str = ""  # path to background image
        self.background_tint: tuple[float, float, float, float] = (1, 1, 1, 1)
        self._bg_texture = None

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h)
            )

        if self.children:
            # Panel wraps first child
            cw, ch = self.children[0].compute_size(viewport_w, viewport_h)
            return (cw + self.padding * 2, ch + self.padding * 2)

        return (self.padding * 2, self.padding * 2)

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float):
        super().layout(x, y, width, height, viewport_w, viewport_h)

        # Inner area after padding
        inner_x = x + self.padding
        inner_y = y + self.padding
        inner_w = width - self.padding * 2
        inner_h = height - self.padding * 2

        for child in self.children:
            cw, ch = child.compute_size(viewport_w, viewport_h)

            # Respect child's anchor within panel's inner area
            anchor = child.anchor
            cx, cy = inner_x, inner_y

            if anchor == "absolute":
                # Absolute positioning relative to panel
                if child.position_x is not None:
                    cx = inner_x + child.position_x.to_pixels(inner_w)
                if child.position_y is not None:
                    cy = inner_y + child.position_y.to_pixels(inner_h)
            else:
                # Anchor-based positioning
                if "left" in anchor:
                    cx = inner_x
                elif "right" in anchor:
                    cx = inner_x + inner_w - cw
                elif "center" in anchor or anchor in ("top", "bottom"):
                    cx = inner_x + (inner_w - cw) / 2

                if "top" in anchor:
                    cy = inner_y
                elif "bottom" in anchor:
                    cy = inner_y + inner_h - ch
                elif "center" in anchor or anchor in ("left", "right"):
                    cy = inner_y + (inner_h - ch) / 2

                # Apply offset
                cx += child.offset_x
                cy += child.offset_y

            child.layout(cx, cy, cw, ch, viewport_w, viewport_h)

    def _ensure_bg_texture(self, renderer: 'UIRenderer'):
        if self._bg_texture is None and self.background_image:
            self._bg_texture = renderer.load_image(self.background_image)

    def render(self, renderer: 'UIRenderer'):
        # Draw background only if not fully transparent
        if self.background_color[3] > 0:
            renderer.draw_rect(
                self.x, self.y, self.width, self.height,
                self.background_color,
                self.border_radius
            )
        # Draw background image on top of color
        if self.background_image:
            self._ensure_bg_texture(renderer)
            if self._bg_texture is not None:
                renderer.draw_image(
                    self.x, self.y, self.width, self.height,
                    self._bg_texture, self.background_tint
                )
        # Render children
        super().render(renderer)
