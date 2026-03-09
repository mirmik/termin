"""VStack container."""

from __future__ import annotations

from tcgui.widgets.widget import Widget


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
            if not child.visible:
                continue
            cw, ch = child.compute_size(viewport_w, viewport_h)
            max_width = max(max_width, cw)
            if not child.stretch:
                total_height += ch

        visible = [c for c in self.children if c.visible]
        if visible:
            total_height += self.spacing * (len(visible) - 1)

        if self.preferred_width:
            max_width = self.preferred_width.to_pixels(viewport_w)
        if self.preferred_height:
            total_height = self.preferred_height.to_pixels(viewport_h)

        return (max_width, total_height)

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float):
        super().layout(x, y, width, height, viewport_w, viewport_h)

        visible = [c for c in self.children if c.visible]
        if not visible:
            return

        # First pass: measure non-stretch children, count stretch children
        fixed_height = 0.0
        stretch_count = 0
        child_heights = []
        for child in visible:
            if child.stretch:
                stretch_count += 1
                child_heights.append(0.0)
            else:
                _, ch = child.compute_size(viewport_w, viewport_h)
                fixed_height += ch
                child_heights.append(ch)

        spacing_total = self.spacing * (len(visible) - 1)
        remaining = max(0.0, height - fixed_height - spacing_total)
        stretch_h = remaining / stretch_count if stretch_count > 0 else 0.0

        # Fill in stretch heights
        for i, child in enumerate(visible):
            if child.stretch:
                child_heights[i] = stretch_h

        # Vertical justify (only meaningful without stretch children)
        total_h = sum(child_heights) + spacing_total
        if self.justify == "center" and stretch_count == 0:
            cy = y + (height - total_h) / 2
        elif self.justify == "end" and stretch_count == 0:
            cy = y + height - total_h
        else:
            cy = y

        for child, ch in zip(visible, child_heights):
            child.layout(x, cy, width, ch, viewport_w, viewport_h)
            cy += ch + self.spacing
