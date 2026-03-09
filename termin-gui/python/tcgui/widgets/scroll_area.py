"""ScrollArea container."""

from __future__ import annotations

from tcgui.widgets.widget import Widget
from tcgui.widgets.events import MouseEvent, MouseWheelEvent
from tcgui.widgets.theme import current_theme as _t


class ScrollArea(Widget):
    """Scrollable container. Wraps a single child and provides vertical/horizontal scrolling."""

    def __init__(self):
        super().__init__()
        self.scroll_x: float = 0.0
        self.scroll_y: float = 0.0
        self.scroll_speed: float = 30.0
        self.show_scrollbar: bool = True
        self.scrollbar_width: float = 8.0
        self.scrollbar_color: tuple[float, float, float, float] = _t.scrollbar
        self.scrollbar_hover_color: tuple[float, float, float, float] = _t.scrollbar_hover

        self._content_w: float = 0.0
        self._content_h: float = 0.0
        self._dragging_scrollbar: bool = False
        self._drag_start_y: float = 0.0
        self._drag_start_scroll: float = 0.0
        self._scrollbar_hovered: bool = False

        # Cached viewport
        self._viewport_w: float = 0
        self._viewport_h: float = 0

    @property
    def _max_scroll_y(self) -> float:
        return max(0.0, self._content_h - self.height)

    @property
    def _max_scroll_x(self) -> float:
        return max(0.0, self._content_w - self.width)

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h),
            )
        w = self.preferred_width.to_pixels(viewport_w) if self.preferred_width else 200
        h = self.preferred_height.to_pixels(viewport_h) if self.preferred_height else 200
        return (w, h)

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float):
        super().layout(x, y, width, height, viewport_w, viewport_h)
        self._viewport_w = viewport_w
        self._viewport_h = viewport_h

        if self.children:
            content = self.children[0]
            # Compute content size using scroll area dimensions as reference,
            # so that relative units (pct/ndc) resolve relative to the
            # scroll area, not the full window viewport.
            cw, ch = content.compute_size(width, height)
            self._content_w = max(cw, width)
            self._content_h = max(ch, height)

            # Clamp scroll
            self.scroll_y = max(0.0, min(self.scroll_y, self._max_scroll_y))
            self.scroll_x = max(0.0, min(self.scroll_x, self._max_scroll_x))

            content.layout(
                x - self.scroll_x,
                y - self.scroll_y,
                width,
                self._content_h,
                viewport_w, viewport_h,
            )

    def render(self, renderer: 'UIRenderer'):
        from tcgui.widgets.theme import current_theme as _t
        renderer.draw_rect(self.x, self.y, self.width, self.height, _t.bg_surface)
        renderer.begin_clip(self.x, self.y, self.width, self.height)

        for child in self.children:
            if child.visible:
                child.render(renderer)

        renderer.end_clip()

        # Draw vertical scrollbar
        if self.show_scrollbar and self._content_h > self.height:
            viewport_ratio = self.height / self._content_h
            thumb_h = max(20.0, self.height * viewport_ratio)
            track_h = self.height - thumb_h
            thumb_y = self.y + (track_h * (self.scroll_y / self._max_scroll_y) if self._max_scroll_y > 0 else 0)
            sb_x = self.x + self.width - self.scrollbar_width

            color = self.scrollbar_hover_color if self._scrollbar_hovered or self._dragging_scrollbar else self.scrollbar_color
            renderer.draw_rect(sb_x, thumb_y, self.scrollbar_width, thumb_h, color, self.scrollbar_width / 2)

    def hit_test(self, px: float, py: float) -> Widget | None:
        if not self.visible:
            return None
        if not self.contains(px, py):
            return None

        # Scrollbar area belongs to ScrollArea itself
        if self.show_scrollbar and self._content_h > self.height:
            sb_x = self.x + self.width - self.scrollbar_width
            if px >= sb_x:
                return self

        # Check children
        for child in reversed(self.children):
            hit = child.hit_test(px, py)
            if hit and hit is not self:
                return hit

        return self

    def on_mouse_wheel(self, event: MouseWheelEvent) -> bool:
        if self._max_scroll_y <= 0:
            return False
        self.scroll_y -= event.dy * self.scroll_speed
        self.scroll_y = max(0.0, min(self.scroll_y, self._max_scroll_y))
        self._relayout_content()
        return True

    def on_mouse_down(self, event: MouseEvent) -> bool:
        # Check if click is on scrollbar
        if self.show_scrollbar and self._content_h > self.height:
            sb_x = self.x + self.width - self.scrollbar_width
            if event.x >= sb_x:
                self._dragging_scrollbar = True
                self._drag_start_y = event.y
                self._drag_start_scroll = self.scroll_y
                return True
        return False

    def on_mouse_move(self, event: MouseEvent):
        if self._dragging_scrollbar:
            delta_y = event.y - self._drag_start_y
            viewport_ratio = self.height / self._content_h
            thumb_h = max(20.0, self.height * viewport_ratio)
            track_h = self.height - thumb_h
            if track_h > 0:
                self.scroll_y = self._drag_start_scroll + delta_y * (self._max_scroll_y / track_h)
                self.scroll_y = max(0.0, min(self.scroll_y, self._max_scroll_y))
                self._relayout_content()
        else:
            # Track scrollbar hover
            if self.show_scrollbar and self._content_h > self.height:
                sb_x = self.x + self.width - self.scrollbar_width
                self._scrollbar_hovered = event.x >= sb_x
            else:
                self._scrollbar_hovered = False

    def on_mouse_up(self, event: MouseEvent):
        self._dragging_scrollbar = False

    def on_mouse_leave(self):
        self._scrollbar_hovered = False

    def _relayout_content(self):
        """Re-position content after scroll change."""
        if self.children:
            content = self.children[0]
            cw, ch = content.compute_size(self.width, self.height)
            self._content_w = max(cw, self.width)
            self._content_h = max(ch, self.height)
            content.layout(
                self.x - self.scroll_x,
                self.y - self.scroll_y,
                self.width,
                self._content_h,
                self._viewport_w, self._viewport_h,
            )
