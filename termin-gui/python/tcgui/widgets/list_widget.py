"""ListWidget widget."""

from __future__ import annotations
import time
from typing import Callable

from tcbase import MouseButton
from tcgui.widgets.widget import Widget
from tcgui.widgets.events import MouseEvent, MouseWheelEvent
from tcgui.widgets.theme import current_theme as _t


class ListWidget(Widget):
    """Vertical list with selectable items, hover highlight, and double-click."""

    def __init__(self):
        super().__init__()
        self._items: list[dict] = []
        self.selected_index: int = -1
        self.item_height: float = 44
        self.item_spacing: float = 2
        self.font_size: float = _t.font_size
        self.subtitle_font_size: float = _t.font_size_small
        self.border_radius: float = _t.border_radius + 1
        self.item_padding: float = 10

        # Colors
        _bif = _t.bg_input_focus
        self.item_background: tuple[float, float, float, float] = (_bif[0], _bif[1], _bif[2], 0.6)
        self.selected_background: tuple[float, float, float, float] = _t.selected
        self.hover_background: tuple[float, float, float, float] = _t.hover_subtle
        self.text_color: tuple[float, float, float, float] = _t.text_primary
        self.subtitle_color: tuple[float, float, float, float] = _t.text_muted
        self.selected_text_color: tuple[float, float, float, float] = _t.text_primary
        self.empty_text: str = "No items"
        self.empty_color: tuple[float, float, float, float] = _t.text_muted

        # Callbacks: (index, item_dict)
        self.on_select: Callable[[int, dict], None] | None = None
        self.on_activate: Callable[[int, dict], None] | None = None
        self.on_context_menu: Callable[[int, dict, float, float], None] | None = None

        # Icon support — set an icon_provider to enable icon rendering
        self.icon_provider = None  # FileIconProvider | None
        self.icon_size: float = 0  # 0 = no icons

        # Internal
        self._scroll_offset: float = 0.0
        self._hovered_index: int = -1
        self._last_click_index: int = -1
        self._last_click_time: float = 0.0
        self._DOUBLE_CLICK_INTERVAL: float = 0.4

    def set_items(self, items: list[dict]) -> None:
        """Set list items. Each dict should have 'text' and optionally 'subtitle', 'data'."""
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

    def _index_at(self, y: float) -> int:
        rel_y = y - self.y + self._scroll_offset
        stride = self.item_height + self.item_spacing
        if stride <= 0:
            return -1
        idx = int(rel_y / stride)
        if 0 <= idx < len(self._items):
            if rel_y - idx * stride <= self.item_height:
                return idx
        return -1

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h),
            )
        w = self.preferred_width.to_pixels(viewport_w) if self.preferred_width else 400
        n = len(self._items)
        h = n * self.item_height + max(0, n - 1) * self.item_spacing if n else self.item_height
        if self.preferred_height:
            h = self.preferred_height.to_pixels(viewport_h)
        return (w, h)

    def render(self, renderer: 'UIRenderer'):
        if not self._items:
            renderer.draw_text(
                self.x + self.item_padding,
                self.y + self.font_size + 4,
                self.empty_text,
                self.empty_color,
                self.font_size,
            )
            return

        renderer.begin_clip(self.x, self.y, self.width, self.height)

        stride = self.item_height + self.item_spacing
        for i, item in enumerate(self._items):
            iy = self.y + i * stride - self._scroll_offset

            # Skip rows outside visible area
            if iy + self.item_height < self.y or iy > self.y + self.height:
                continue

            # Background
            if i == self.selected_index:
                bg = self.selected_background
            elif i == self._hovered_index:
                bg = self.hover_background
            else:
                bg = self.item_background

            renderer.draw_rect(
                self.x, iy, self.width, self.item_height, bg, self.border_radius
            )

            # Text colors
            tc = self.selected_text_color if i == self.selected_index else self.text_color

            text = item.get("text", "")
            subtitle = item.get("subtitle", "")

            # Icon
            text_x = self.x + self.item_padding
            if self.icon_provider is not None and self.icon_size > 0:
                icon_type = item.get("icon_type")
                if icon_type:
                    tex = self.icon_provider.get_texture(renderer, icon_type)
                    if tex is not None:
                        icon_y = iy + (self.item_height - self.icon_size) / 2
                        renderer.draw_image(
                            self.x + self.item_padding, icon_y,
                            self.icon_size, self.icon_size, tex,
                        )
                        text_x = self.x + self.item_padding + self.icon_size + 6

            if subtitle:
                renderer.draw_text(
                    text_x,
                    iy + self.font_size + 4,
                    text, tc, self.font_size,
                )
                renderer.draw_text(
                    text_x,
                    iy + self.font_size + self.subtitle_font_size + 8,
                    subtitle, self.subtitle_color, self.subtitle_font_size,
                )
            else:
                renderer.draw_text(
                    text_x,
                    iy + self.item_height / 2 + self.font_size / 3,
                    text, tc, self.font_size,
                )

        renderer.end_clip()

    # --- Mouse events ---

    def on_mouse_wheel(self, event: MouseWheelEvent) -> bool:
        """Scroll list with mouse wheel."""
        n = len(self._items)
        if n == 0:
            return False
        stride = self.item_height + self.item_spacing
        total_content = n * stride
        max_scroll = max(0.0, total_content - self.height)
        if max_scroll <= 0:
            return False
        self._scroll_offset -= event.dy * 30
        self._scroll_offset = max(0.0, min(self._scroll_offset, max_scroll))
        return True

    def on_mouse_move(self, event: MouseEvent):
        self._hovered_index = self._index_at(event.y)

    def on_mouse_leave(self):
        self._hovered_index = -1

    def on_mouse_down(self, event: MouseEvent) -> bool:
        idx = self._index_at(event.y)
        if event.button == MouseButton.RIGHT:
            if self.on_context_menu:
                if idx >= 0:
                    self.selected_index = idx
                    if self.on_select:
                        self.on_select(idx, self._items[idx])
                    self.on_context_menu(idx, self._items[idx], event.x, event.y)
                else:
                    self.on_context_menu(-1, {}, event.x, event.y)
                return True
            if idx >= 0:
                self.selected_index = idx
                if self.on_select:
                    self.on_select(idx, self._items[idx])
                return True
            return False

        if idx < 0:
            return False

        now = time.monotonic()

        # Double-click detection
        if (idx == self._last_click_index
                and now - self._last_click_time < self._DOUBLE_CLICK_INTERVAL):
            if self.on_activate:
                self.on_activate(idx, self._items[idx])
            self._last_click_index = -1
            self._last_click_time = 0.0
            return True

        # Single click — select
        self._last_click_index = idx
        self._last_click_time = now
        self.selected_index = idx
        if self.on_select:
            self.on_select(idx, self._items[idx])
        return True
