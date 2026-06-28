"""HStack container."""

from __future__ import annotations

from tcgui.widgets.widget import Widget


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
            if not child.visible:
                continue
            cw, ch = child.compute_size(viewport_w, viewport_h)
            total_width += cw
            max_height = max(max_height, ch)

        visible = [c for c in self.children if c.visible]
        if visible:
            total_width += self.spacing * (len(visible) - 1)

        # Allow override of individual dimensions
        if self.preferred_width:
            total_width = self.preferred_width.to_pixels(viewport_w)
        if self.preferred_height:
            max_height = self.preferred_height.to_pixels(viewport_h)

        return (total_width, max_height)

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float):
        super().layout(x, y, width, height, viewport_w, viewport_h)

        visible = [c for c in self.children if c.visible]
        if not visible:
            return

        # First pass: measure every child. Non-stretch children keep their
        # natural width. Stretch children use natural width as a soft
        # preference: it biases layout when there is room, but it must not
        # force the container to overflow.
        fixed_width = 0.0
        stretch_pref_width = 0.0
        stretch_count = 0
        child_widths = []
        for child in visible:
            cw, _ = child.compute_size(viewport_w, viewport_h)
            child_widths.append(cw)
            if child.stretch:
                stretch_pref_width += cw
                stretch_count += 1
            else:
                fixed_width += cw

        spacing_total = self.spacing * (len(visible) - 1)
        available_stretch_width = max(0.0, width - fixed_width - spacing_total)

        if stretch_count > 0:
            if stretch_pref_width <= available_stretch_width:
                stretch_extra_w = (available_stretch_width - stretch_pref_width) / stretch_count
                for i, child in enumerate(visible):
                    if child.stretch:
                        child_widths[i] += stretch_extra_w
            else:
                stretch_w = available_stretch_width / stretch_count
                for i, child in enumerate(visible):
                    if child.stretch:
                        child_widths[i] = stretch_w

        # Horizontal justify (only meaningful without stretch children)
        total_w = sum(child_widths) + spacing_total
        if self.justify == "center" and stretch_count == 0:
            cx = x + (width - total_w) / 2
        elif self.justify == "end" and stretch_count == 0:
            cx = x + width - total_w
        else:
            cx = x

        for child, cw in zip(visible, child_widths, strict=True):
            child.layout(cx, y, cw, height, viewport_w, viewport_h)
            cx += cw + self.spacing
