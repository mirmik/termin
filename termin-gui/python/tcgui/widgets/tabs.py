"""Tab widgets: TabBar, TabView."""

from __future__ import annotations

from typing import Callable

from tcgui.widgets.widget import Widget
from tcgui.widgets.events import MouseEvent
from tcgui.widgets.theme import current_theme as _t


class TabBar(Widget):
    """Horizontal bar with clickable tabs."""

    def __init__(self):
        super().__init__()
        self.tabs: list[str] = []
        self.selected_index: int = 0
        self.tab_padding: float = 12.0
        self.tab_spacing: float = 2.0
        self.font_size: float = 14.0

        _bg = _t.bg_surface
        self.tab_color: tuple[float, float, float, float] = _bg
        self.selected_tab_color: tuple[float, float, float, float] = _t.hover_subtle
        self.hover_tab_color: tuple[float, float, float, float] = (_bg[0] + 0.05, _bg[1] + 0.05, _bg[2] + 0.05, _bg[3])
        self.text_color: tuple[float, float, float, float] = _t.text_secondary
        self.selected_text_color: tuple[float, float, float, float] = _t.text_primary
        self.indicator_color: tuple[float, float, float, float] = _t.accent
        self.indicator_height: float = 2.0
        self.border_radius: float = _t.border_radius + 1

        # State
        self._hovered_index: int = -1
        self._tab_rects: list[tuple[float, float, float, float]] = []

        # Callback
        self.on_changed: Callable[[int], None] | None = None

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h),
            )
        w = self.preferred_width.to_pixels(viewport_w) if self.preferred_width else 400
        h = self.font_size + self.tab_padding * 2 + self.indicator_height
        return (w, h)

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float):
        super().layout(x, y, width, height, viewport_w, viewport_h)
        self._compute_tab_rects()

    def _compute_tab_rects(self):
        """Compute bounding rectangles for each tab."""
        self._tab_rects = []
        cx = self.x
        tab_h = self.height - self.indicator_height
        for title in self.tabs:
            tw = len(title) * self.font_size * 0.6 + self.tab_padding * 2
            self._tab_rects.append((cx, self.y, tw, tab_h))
            cx += tw + self.tab_spacing

    def _index_at(self, x: float, y: float) -> int:
        for i, (rx, ry, rw, rh) in enumerate(self._tab_rects):
            if rx <= x < rx + rw and ry <= y < ry + rh:
                return i
        return -1

    def render(self, renderer: 'UIRenderer'):
        tab_h = self.height - self.indicator_height

        for i, (title, (rx, ry, rw, rh)) in enumerate(zip(self.tabs, self._tab_rects)):
            # Tab background
            if i == self.selected_index:
                bg = self.selected_tab_color
            elif i == self._hovered_index:
                bg = self.hover_tab_color
            else:
                bg = self.tab_color

            renderer.draw_rect(rx, ry, rw, rh, bg, self.border_radius)

            # Tab text
            tc = self.selected_text_color if i == self.selected_index else self.text_color
            renderer.draw_text_centered(
                rx + rw / 2, ry + rh / 2,
                title, tc, self.font_size
            )

            # Indicator under selected tab
            if i == self.selected_index:
                renderer.draw_rect(
                    rx, ry + rh, rw, self.indicator_height,
                    self.indicator_color
                )

    def on_mouse_move(self, event: MouseEvent):
        self._hovered_index = self._index_at(event.x, event.y)

    def on_mouse_leave(self):
        self._hovered_index = -1

    def on_mouse_down(self, event: MouseEvent) -> bool:
        idx = self._index_at(event.x, event.y)
        if idx >= 0 and idx != self.selected_index:
            self.selected_index = idx
            if self.on_changed:
                self.on_changed(idx)
            return True
        return idx >= 0


class TabView(Widget):
    """TabBar + content panel. Shows one child widget per tab."""

    def __init__(self):
        super().__init__()
        self.tab_bar: TabBar = TabBar()
        self.tab_position: str = "top"  # top | bottom
        self.pages: list[Widget] = []

        # Keep tab_bar in children so parent/_ui propagation works.
        self.add_child(self.tab_bar)
        self.tab_bar.on_changed = self._on_tab_change

        # Cached viewport
        self._viewport_w: float = 0
        self._viewport_h: float = 0

    @property
    def selected_index(self) -> int:
        return self.tab_bar.selected_index

    @selected_index.setter
    def selected_index(self, value: int):
        if 0 <= value < len(self.pages):
            self.tab_bar.selected_index = value

    def add_tab(self, title: str, content: Widget):
        """Add a tab with title and content widget."""
        self.tab_bar.tabs.append(title)
        self.add_child(content)
        self.pages.append(content)

    def remove_tab(self, index: int):
        """Remove tab at index."""
        if 0 <= index < len(self.pages):
            self.tab_bar.tabs.pop(index)
            page = self.pages.pop(index)
            self.remove_child(page)
            if self.tab_bar.selected_index >= len(self.pages):
                self.tab_bar.selected_index = max(0, len(self.pages) - 1)

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h),
            )
        w = self.preferred_width.to_pixels(viewport_w) if self.preferred_width else 400
        h = self.preferred_height.to_pixels(viewport_h) if self.preferred_height else 300
        return (w, h)

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float):
        super().layout(x, y, width, height, viewport_w, viewport_h)
        self._viewport_w = viewport_w
        self._viewport_h = viewport_h

        _, bar_h = self.tab_bar.compute_size(viewport_w, viewport_h)

        if self.tab_position == "bottom":
            # Content on top, tabs at bottom
            content_y = y
            content_h = height - bar_h
            bar_y = y + content_h
        else:
            # Tabs on top, content below
            bar_y = y
            content_y = y + bar_h
            content_h = height - bar_h

        self.tab_bar.layout(x, bar_y, width, bar_h, viewport_w, viewport_h)

        # Layout all pages but only the active one will be rendered
        for i, page in enumerate(self.pages):
            page.visible = (i == self.tab_bar.selected_index)
            if page.visible:
                cw, ch = page.compute_size(viewport_w, viewport_h)
                page.layout(x, content_y, width, content_h, viewport_w, viewport_h)

    def render(self, renderer: 'UIRenderer'):
        from tcgui.widgets.theme import current_theme as _t
        renderer.draw_rect(self.x, self.y, self.width, self.height, _t.bg_surface)
        self.tab_bar.render(renderer)

        idx = self.tab_bar.selected_index
        if 0 <= idx < len(self.pages):
            page = self.pages[idx]
            if page.visible:
                page.render(renderer)

    def hit_test(self, px: float, py: float) -> Widget | None:
        if not self.visible:
            return None
        if not self.contains(px, py):
            return None

        # Check tab bar
        if self.tab_bar.contains(px, py):
            return self.tab_bar

        # Check active page
        idx = self.tab_bar.selected_index
        if 0 <= idx < len(self.pages):
            page = self.pages[idx]
            hit = page.hit_test(px, py)
            if hit:
                return hit

        return self

    def _on_tab_change(self, index: int):
        """Internal callback when tab changes — re-layout pages."""
        for i, page in enumerate(self.pages):
            page.visible = (i == index)
            if page.visible:
                _, bar_h = self.tab_bar.compute_size(self._viewport_w, self._viewport_h)
                if self.tab_position == "bottom":
                    content_y = self.y
                    content_h = self.height - bar_h
                else:
                    content_y = self.y + bar_h
                    content_h = self.height - bar_h
                cw, ch = page.compute_size(self._viewport_w, self._viewport_h)
                page.layout(
                    self.x, content_y, self.width, content_h,
                    self._viewport_w, self._viewport_h,
                )
