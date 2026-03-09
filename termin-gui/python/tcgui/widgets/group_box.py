"""GroupBox container."""

from __future__ import annotations
from typing import Callable

from tcgui.widgets.widget import Widget
from tcgui.widgets.events import MouseEvent
from tcgui.widgets.theme import current_theme as _t


class GroupBox(Widget):
    """Collapsible section with a title header."""

    def __init__(self):
        super().__init__()
        self.title: str = ""
        self.expanded: bool = True
        self.title_height: float = 28
        self.content_padding: float = 8
        self.spacing: float = _t.spacing
        self.title_padding: float = 8
        self.font_size: float = _t.font_size
        self.border_radius: float = _t.border_radius

        # Colors
        self.background_color: tuple[float, float, float, float] = _t.bg_group
        self.title_background_color: tuple[float, float, float, float] = _t.bg_surface
        self.title_hover_color: tuple[float, float, float, float] = _t.hover_subtle
        self.title_text_color: tuple[float, float, float, float] = _t.text_primary
        self.arrow_color: tuple[float, float, float, float] = _t.text_secondary
        self.border_color: tuple[float, float, float, float] = _t.border

        # State
        self._title_hovered: bool = False
        self._viewport_w: float = 0
        self._viewport_h: float = 0

        # Callback
        self.on_toggle: Callable[[bool], None] | None = None

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        w = self.preferred_width.to_pixels(viewport_w) if self.preferred_width else 300

        if not self.expanded:
            return (w, self.title_height)

        child_h = 0.0
        visible_count = 0
        for child in self.children:
            if not child.visible:
                continue
            _, ch = child.compute_size(viewport_w, viewport_h)
            child_h += ch
            visible_count += 1
        if visible_count > 1:
            child_h += self.spacing * (visible_count - 1)
        h = self.title_height + child_h + self.content_padding * 2

        if self.preferred_height:
            h = self.preferred_height.to_pixels(viewport_h)
        return (w, h)

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float):
        if not self.expanded:
            super().layout(x, y, width, self.title_height, viewport_w, viewport_h)
            return

        super().layout(x, y, width, height, viewport_w, viewport_h)
        self._viewport_w = viewport_w
        self._viewport_h = viewport_h

        cx = x + self.content_padding
        cy = y + self.title_height + self.content_padding
        cw = width - self.content_padding * 2
        for child in self.children:
            if not child.visible:
                continue
            _, ch = child.compute_size(viewport_w, viewport_h)
            child.layout(cx, cy, cw, ch, viewport_w, viewport_h)
            cy += ch + self.spacing

    def render(self, renderer: 'UIRenderer'):
        # Border
        renderer.draw_rect(self.x, self.y, self.width, self.height, self.border_color, self.border_radius)

        # Background (inset by 1)
        renderer.draw_rect(
            self.x + 1, self.y + 1,
            self.width - 2, self.height - 2,
            self.background_color, max(0, self.border_radius - 1)
        )

        # Title bar
        title_bg = self.title_hover_color if self._title_hovered else self.title_background_color
        renderer.draw_rect(
            self.x + 1, self.y + 1,
            self.width - 2, self.title_height - 1,
            title_bg, max(0, self.border_radius - 1)
        )

        # Arrow indicator
        arrow = "\u25BC" if self.expanded else "\u25B6"
        arrow_x = self.x + self.title_padding + 6
        arrow_y = self.y + self.title_height / 2
        renderer.draw_text_centered(arrow_x, arrow_y, arrow, self.arrow_color, self.font_size * 0.6)

        # Title text
        text_x = self.x + self.title_padding + 18
        text_y = self.y + self.title_height / 2 + self.font_size * 0.35
        renderer.draw_text(text_x, text_y, self.title, self.title_text_color, self.font_size)

        # Children (only if expanded)
        if self.expanded:
            for child in self.children:
                if child.visible:
                    child.render(renderer)

    def hit_test(self, px: float, py: float) -> Widget | None:
        if not self.visible:
            return None
        if not self.contains(px, py):
            return None

        # Title area → self
        if py < self.y + self.title_height:
            return self

        # Content area → delegate to children
        if self.expanded:
            for child in reversed(self.children):
                hit = child.hit_test(px, py)
                if hit:
                    return hit
        return self

    def on_mouse_move(self, event: MouseEvent):
        self._title_hovered = event.y < self.y + self.title_height

    def on_mouse_leave(self):
        self._title_hovered = False

    def on_mouse_down(self, event: MouseEvent) -> bool:
        if event.y < self.y + self.title_height:
            self.expanded = not self.expanded
            if self._ui is not None:
                self._ui.request_layout()
            if self.on_toggle:
                self.on_toggle(self.expanded)
            return True
        return False
