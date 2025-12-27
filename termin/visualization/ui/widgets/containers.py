"""Container widgets: HStack, VStack, Panel."""

from __future__ import annotations

from termin.visualization.ui.widgets.widget import Widget
from termin.visualization.ui.widgets.units import Value, px


class HStack(Widget):
    """Horizontal layout container."""

    def __init__(self):
        super().__init__()
        self.spacing: float = 0  # pixels
        self.alignment: str = "center"  # top, center, bottom (vertical)
        self.justify: str = "start"  # start, center, end (horizontal)

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h)
            )

        total_width = 0.0
        max_height = 0.0

        for child in self.children:
            cw, ch = child.compute_size(viewport_w, viewport_h)
            total_width += cw
            max_height = max(max_height, ch)

        if self.children:
            total_width += self.spacing * (len(self.children) - 1)

        # Allow override of individual dimensions
        if self.preferred_width:
            total_width = self.preferred_width.to_pixels(viewport_w)
        if self.preferred_height:
            max_height = self.preferred_height.to_pixels(viewport_h)

        return (total_width, max_height)

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float):
        super().layout(x, y, width, height, viewport_w, viewport_h)

        # Calculate total content width
        total_content_width = 0.0
        for child in self.children:
            cw, _ = child.compute_size(viewport_w, viewport_h)
            total_content_width += cw
        if self.children:
            total_content_width += self.spacing * (len(self.children) - 1)

        # Horizontal justify
        if self.justify == "center":
            cx = x + (width - total_content_width) / 2
        elif self.justify == "end":
            cx = x + width - total_content_width
        else:  # start
            cx = x

        for child in self.children:
            cw, ch = child.compute_size(viewport_w, viewport_h)

            # Vertical alignment
            if self.alignment == "top":
                cy = y
            elif self.alignment == "bottom":
                cy = y + height - ch
            else:  # center
                cy = y + (height - ch) / 2

            child.layout(cx, cy, cw, ch, viewport_w, viewport_h)
            cx += cw + self.spacing


class VStack(Widget):
    """Vertical layout container."""

    def __init__(self):
        super().__init__()
        self.spacing: float = 0  # pixels
        self.alignment: str = "center"  # left, center, right (horizontal)
        self.justify: str = "start"  # start, center, end (vertical)

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h)
            )

        max_width = 0.0
        total_height = 0.0

        for child in self.children:
            cw, ch = child.compute_size(viewport_w, viewport_h)
            max_width = max(max_width, cw)
            total_height += ch

        if self.children:
            total_height += self.spacing * (len(self.children) - 1)

        if self.preferred_width:
            max_width = self.preferred_width.to_pixels(viewport_w)
        if self.preferred_height:
            total_height = self.preferred_height.to_pixels(viewport_h)

        return (max_width, total_height)

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float):
        super().layout(x, y, width, height, viewport_w, viewport_h)

        # Calculate total content height
        total_content_height = 0.0
        for child in self.children:
            _, ch = child.compute_size(viewport_w, viewport_h)
            total_content_height += ch
        if self.children:
            total_content_height += self.spacing * (len(self.children) - 1)

        # Vertical justify
        if self.justify == "center":
            cy = y + (height - total_content_height) / 2
        elif self.justify == "end":
            cy = y + height - total_content_height
        else:  # start
            cy = y

        for child in self.children:
            cw, ch = child.compute_size(viewport_w, viewport_h)

            # Horizontal alignment
            if self.alignment == "left":
                cx = x
            elif self.alignment == "right":
                cx = x + width - cw
            else:  # center
                cx = x + (width - cw) / 2

            child.layout(cx, cy, cw, ch, viewport_w, viewport_h)
            cy += ch + self.spacing


class Panel(Widget):
    """Container with background and padding."""

    def __init__(self):
        super().__init__()
        self.padding: float = 0  # pixels
        self.background_color: tuple[float, float, float, float] = (0.2, 0.2, 0.2, 0.9)
        self.border_radius: float = 0

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

    def render(self, renderer: 'UIRenderer'):
        # Draw background only if not fully transparent
        if self.background_color[3] > 0:
            renderer.draw_rect(
                self.x, self.y, self.width, self.height,
                self.background_color,
                self.border_radius
            )
        # Render children
        super().render(renderer)
