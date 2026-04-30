"""FileGridWidget widget."""

from __future__ import annotations

import math
import time
from typing import Callable

from tcbase import MouseButton
from tcgui.widgets.events import MouseEvent, MouseWheelEvent
from tcgui.widgets.theme import current_theme as _t
from tcgui.widgets.widget import Widget


class FileGridWidget(Widget):
    """Icon grid with selectable items, hover highlight, and double-click."""

    def __init__(self):
        super().__init__()
        self._items: list[dict] = []
        self.selected_index: int = -1

        self.tile_width: float = 86.0
        self.tile_height: float = 82.0
        self.tile_spacing: float = 8.0
        self.padding: float = 8.0
        self.icon_size: float = 34.0
        self.font_size: float = _t.font_size
        self.subtitle_font_size: float = _t.font_size_small
        self.border_radius: float = _t.border_radius + 1

        self.background_color: tuple[float, float, float, float] = _t.bg_input
        self.tile_background: tuple[float, float, float, float] = (_t.bg_input[0], _t.bg_input[1], _t.bg_input[2], 0.0)
        self.selected_background: tuple[float, float, float, float] = _t.selected
        self.hover_background: tuple[float, float, float, float] = _t.hover_subtle
        self.text_color: tuple[float, float, float, float] = _t.text_primary
        self.subtitle_color: tuple[float, float, float, float] = _t.text_muted
        self.selected_text_color: tuple[float, float, float, float] = _t.text_primary
        self.empty_text: str = "No items"
        self.empty_color: tuple[float, float, float, float] = _t.text_muted

        self.on_select: Callable[[int, dict], None] | None = None
        self.on_activate: Callable[[int, dict], None] | None = None
        self.on_context_menu: Callable[[int, dict, float, float], None] | None = None

        self.icon_provider = None

        self._scroll_offset: float = 0.0
        self._hovered_index: int = -1
        self._last_click_index: int = -1
        self._last_click_time: float = 0.0
        self._DOUBLE_CLICK_INTERVAL: float = 0.4

    def set_items(self, items: list[dict]) -> None:
        """Set grid items. Each dict should have 'text' and optionally 'subtitle', 'data'."""
        self._items = list(items)
        self._scroll_offset = 0.0
        self._hovered_index = -1
        if self.selected_index >= len(self._items):
            self.selected_index = -1

    @property
    def items(self) -> list[dict]:
        return self._items

    @property
    def selected_item(self) -> dict | None:
        if 0 <= self.selected_index < len(self._items):
            return self._items[self.selected_index]
        return None

    def _column_count(self) -> int:
        usable_w = max(1.0, self.width - self.padding * 2.0)
        stride = self.tile_width + self.tile_spacing
        return max(1, int((usable_w + self.tile_spacing) / stride))

    def _content_height(self) -> float:
        if not self._items:
            return self.tile_height + self.padding * 2.0
        cols = self._column_count()
        rows = int(math.ceil(len(self._items) / cols))
        return self.padding * 2.0 + rows * self.tile_height + max(0, rows - 1) * self.tile_spacing

    def _item_rect(self, index: int) -> tuple[float, float, float, float]:
        cols = self._column_count()
        col = index % cols
        row = index // cols
        x = self.x + self.padding + col * (self.tile_width + self.tile_spacing)
        y = self.y + self.padding + row * (self.tile_height + self.tile_spacing) - self._scroll_offset
        return (x, y, self.tile_width, self.tile_height)

    def _index_at(self, x: float, y: float) -> int:
        rel_x = x - self.x - self.padding
        rel_y = y - self.y - self.padding + self._scroll_offset
        if rel_x < 0 or rel_y < 0:
            return -1
        col_stride = self.tile_width + self.tile_spacing
        row_stride = self.tile_height + self.tile_spacing
        col = int(rel_x / col_stride)
        row = int(rel_y / row_stride)
        if rel_x - col * col_stride > self.tile_width:
            return -1
        if rel_y - row * row_stride > self.tile_height:
            return -1
        index = row * self._column_count() + col
        if 0 <= index < len(self._items):
            return index
        return -1

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h),
            )
        w = self.preferred_width.to_pixels(viewport_w) if self.preferred_width else 400.0
        h = self.preferred_height.to_pixels(viewport_h) if self.preferred_height else self._content_height()
        return (w, h)

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float):
        super().layout(x, y, width, height, viewport_w, viewport_h)
        max_scroll = max(0.0, self._content_height() - self.height)
        self._scroll_offset = max(0.0, min(self._scroll_offset, max_scroll))

    def render(self, renderer: 'UIRenderer'):
        renderer.draw_rect(
            self.x, self.y, self.width, self.height,
            self.background_color, self.border_radius,
        )

        if not self._items:
            renderer.draw_text(
                self.x + self.padding,
                self.y + self.font_size + self.padding,
                self.empty_text,
                self.empty_color,
                self.font_size,
            )
            return

        renderer.begin_clip(self.x, self.y, self.width, self.height)

        for i, item in enumerate(self._items):
            ix, iy, iw, ih = self._item_rect(i)
            if iy + ih < self.y or iy > self.y + self.height:
                continue

            if i == self.selected_index:
                bg = self.selected_background
            elif i == self._hovered_index:
                bg = self.hover_background
            else:
                bg = self.tile_background

            if bg[3] > 0:
                renderer.draw_rect(ix, iy, iw, ih, bg, self.border_radius)

            icon_type = item.get("icon_type")
            if self.icon_provider is not None and icon_type:
                tex = self.icon_provider.get_texture(renderer, icon_type)
                if tex is not None:
                    icon_x = ix + (iw - self.icon_size) / 2.0
                    icon_y = iy + 8.0
                    renderer.draw_image(icon_x, icon_y, self.icon_size, self.icon_size, tex)

            tc = self.selected_text_color if i == self.selected_index else self.text_color
            name = item.get("text", "")
            subtitle = item.get("subtitle", "")
            text_y = iy + 8.0 + self.icon_size + self.font_size + 8.0
            self._draw_centered_elided(renderer, ix + 5.0, text_y, iw - 10.0, name, tc, self.font_size)
            if subtitle:
                sub_y = text_y + self.subtitle_font_size + 5.0
                self._draw_centered_elided(renderer, ix + 5.0, sub_y, iw - 10.0, subtitle, self.subtitle_color, self.subtitle_font_size)

        renderer.end_clip()

    def _draw_centered_elided(
        self,
        renderer: 'UIRenderer',
        x: float,
        baseline_y: float,
        max_width: float,
        text: str,
        color: tuple[float, float, float, float],
        font_size: float,
    ) -> None:
        if not text:
            return
        text_width, _ = renderer.measure_text(text, font_size)
        draw_text = text
        if text_width > max_width:
            ellipsis = "..."
            available = max(0.0, max_width - renderer.measure_text(ellipsis, font_size)[0])
            while draw_text and renderer.measure_text(draw_text, font_size)[0] > available:
                draw_text = draw_text[:-1]
            draw_text = draw_text + ellipsis if draw_text else ellipsis
            text_width, _ = renderer.measure_text(draw_text, font_size)
        renderer.draw_text(x + (max_width - text_width) / 2.0, baseline_y, draw_text, color, font_size)

    def on_mouse_wheel(self, event: MouseWheelEvent) -> bool:
        if not self._items:
            return False
        max_scroll = max(0.0, self._content_height() - self.height)
        if max_scroll <= 0:
            return False
        self._scroll_offset -= event.dy * 30.0
        self._scroll_offset = max(0.0, min(self._scroll_offset, max_scroll))
        return True

    def on_mouse_move(self, event: MouseEvent):
        self._hovered_index = self._index_at(event.x, event.y)

    def on_mouse_leave(self):
        self._hovered_index = -1

    def on_mouse_down(self, event: MouseEvent) -> bool:
        idx = self._index_at(event.x, event.y)
        if event.button == MouseButton.RIGHT:
            if self.on_context_menu is not None:
                if idx >= 0:
                    self.selected_index = idx
                    if self.on_select is not None:
                        self.on_select(idx, self._items[idx])
                    self.on_context_menu(idx, self._items[idx], event.x, event.y)
                else:
                    self.on_context_menu(-1, {}, event.x, event.y)
                return True
            if idx >= 0:
                self.selected_index = idx
                if self.on_select is not None:
                    self.on_select(idx, self._items[idx])
                return True
            return False

        if idx < 0:
            return False

        now = time.monotonic()
        if idx == self._last_click_index and now - self._last_click_time < self._DOUBLE_CLICK_INTERVAL:
            if self.on_activate is not None:
                self.on_activate(idx, self._items[idx])
            self._last_click_index = -1
            self._last_click_time = 0.0
            return True

        self._last_click_index = idx
        self._last_click_time = now
        self.selected_index = idx
        if self.on_select is not None:
            self.on_select(idx, self._items[idx])
        return True
