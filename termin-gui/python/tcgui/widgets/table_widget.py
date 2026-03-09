"""TableWidget — multi-column table with headers, selection, and column resize."""

from __future__ import annotations

import time
from typing import Any, Callable

from tcgui.widgets.widget import Widget
from tcgui.widgets.events import MouseEvent, MouseWheelEvent
from tcgui.widgets.theme import current_theme as _t


class TableColumn:
    """Column definition for TableWidget."""

    def __init__(self, header: str, width: float = 0, min_width: float = 40):
        self.header: str = header
        self.width: float = width  # 0 = stretch
        self.min_width: float = min_width


class TableWidget(Widget):
    """Multi-column table with selectable rows, headers, and column drag-resize."""

    def __init__(self):
        super().__init__()

        self._columns: list[TableColumn] = []
        self._rows: list[list[str]] = []
        self._row_data: list[Any] = []

        # Selection
        self.selected_index: int = -1

        # Metrics
        self.row_height: float = 24
        self.header_height: float = 24
        self.font_size: float = 12
        self.header_font_size: float = 11
        self.cell_padding: float = 6

        # Colors
        self.header_background: tuple[float, float, float, float] = _t.bg_surface
        self.header_text_color: tuple[float, float, float, float] = _t.text_muted
        self.header_border_color: tuple[float, float, float, float] = (
            _t.border[0], _t.border[1], _t.border[2], 0.5,
        )
        _bif = _t.bg_input_focus
        self.row_background: tuple[float, float, float, float] = (
            _bif[0], _bif[1], _bif[2], 0.3,
        )
        self.row_alt_background: tuple[float, float, float, float] = (
            _bif[0], _bif[1], _bif[2], 0.15,
        )
        self.selected_background: tuple[float, float, float, float] = _t.selected
        self.hover_background: tuple[float, float, float, float] = _t.hover_subtle
        self.text_color: tuple[float, float, float, float] = _t.text_primary
        self.selected_text_color: tuple[float, float, float, float] = _t.text_primary
        self.empty_text: str = "No data"
        self.empty_color: tuple[float, float, float, float] = _t.text_muted

        # Callbacks
        self.on_select: Callable[[int, Any], None] | None = None
        self.on_activate: Callable[[int, Any], None] | None = None

        # Scroll
        self._scroll_offset: float = 0.0

        # Hover
        self._hovered_index: int = -1

        # Double-click
        self._last_click_index: int = -1
        self._last_click_time: float = 0.0
        self._DOUBLE_CLICK_INTERVAL: float = 0.4

        # Column resize drag
        self._resizing: bool = False
        self._resize_col_index: int = -1
        self._resize_start_x: float = 0.0
        self._resize_start_width: float = 0.0
        self._RESIZE_ZONE: float = 4.0

        # Cached column positions (recomputed in render)
        self._col_x: list[float] = []
        self._col_w: list[float] = []

    def set_columns(self, columns: list[TableColumn]) -> None:
        self._columns = list(columns)
        self._col_x = []
        self._col_w = []

    def set_rows(self, rows: list[list[str]], data: list[Any] | None = None) -> None:
        self._rows = list(rows)
        self._row_data = list(data) if data is not None else [None] * len(rows)
        self._scroll_offset = 0.0
        self._hovered_index = -1
        if self.selected_index >= len(self._rows):
            self.selected_index = -1

    @property
    def selected_data(self) -> Any:
        if 0 <= self.selected_index < len(self._row_data):
            return self._row_data[self.selected_index]
        return None

    # --- Column layout ---

    def _compute_col_layout(self, total_width: float) -> None:
        if not self._columns:
            self._col_x = []
            self._col_w = []
            return

        n = len(self._columns)
        widths = [0.0] * n
        fixed_total = 0.0
        stretch_count = 0

        for i, col in enumerate(self._columns):
            if col.width > 0:
                widths[i] = col.width
                fixed_total += col.width
            else:
                stretch_count += 1

        remaining = max(0.0, total_width - fixed_total)
        stretch_each = remaining / stretch_count if stretch_count > 0 else 0.0

        for i, col in enumerate(self._columns):
            if col.width == 0:
                widths[i] = max(col.min_width, stretch_each)

        self._col_w = widths
        self._col_x = [0.0] * n
        cx = 0.0
        for i in range(n):
            self._col_x[i] = cx
            cx += widths[i]

    # --- Row index at y ---

    def _index_at(self, y: float) -> int:
        body_top = self.y + self.header_height
        rel_y = y - body_top + self._scroll_offset
        if rel_y < 0:
            return -1
        idx = int(rel_y / self.row_height)
        if 0 <= idx < len(self._rows):
            if rel_y - idx * self.row_height <= self.row_height:
                return idx
        return -1

    def _col_at_border(self, x: float) -> int:
        """Return column index if x is near a column right edge (for resize), else -1.

        Skips the last column (nothing to the right to redistribute).
        """
        rel_x = x - self.x
        for i in range(len(self._col_x) - 1):
            right_edge = self._col_x[i] + self._col_w[i]
            if abs(rel_x - right_edge) <= self._RESIZE_ZONE:
                return i
        return -1

    # --- Widget overrides ---

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h),
            )
        w = self.preferred_width.to_pixels(viewport_w) if self.preferred_width else 400
        n = len(self._rows)
        h = self.header_height + n * self.row_height if n else self.header_height + self.row_height
        if self.preferred_height:
            h = self.preferred_height.to_pixels(viewport_h)
        return (w, h)

    def render(self, renderer: 'UIRenderer'):
        self._compute_col_layout(self.width)

        renderer.begin_clip(self.x, self.y, self.width, self.height)

        self._render_header(renderer)
        self._render_rows(renderer)

        renderer.end_clip()

    def _render_header(self, renderer: 'UIRenderer') -> None:
        hx = self.x
        hy = self.y
        hw = self.width
        hh = self.header_height

        renderer.draw_rect(hx, hy, hw, hh, self.header_background)

        for i, col in enumerate(self._columns):
            cx = hx + self._col_x[i]
            cw = self._col_w[i]

            renderer.begin_clip(cx, hy, cw, hh)
            renderer.draw_text(
                cx + self.cell_padding,
                hy + hh / 2 + self.header_font_size / 3,
                col.header,
                self.header_text_color,
                self.header_font_size,
            )
            renderer.end_clip()

            # Column separator
            if i < len(self._columns) - 1:
                sep_x = cx + cw
                renderer.draw_line(
                    sep_x, hy + 2, sep_x, hy + hh - 2,
                    self.header_border_color, 1.0,
                )

        # Bottom border
        renderer.draw_line(
            hx, hy + hh, hx + hw, hy + hh,
            self.header_border_color, 1.0,
        )

    def _render_rows(self, renderer: 'UIRenderer') -> None:
        if not self._rows:
            renderer.draw_text(
                self.x + self.cell_padding,
                self.y + self.header_height + self.font_size + 4,
                self.empty_text,
                self.empty_color,
                self.font_size,
            )
            return

        body_top = self.y + self.header_height
        body_height = self.height - self.header_height

        renderer.begin_clip(self.x, body_top, self.width, body_height)

        for i, row in enumerate(self._rows):
            ry = body_top + i * self.row_height - self._scroll_offset

            if ry + self.row_height < body_top or ry > body_top + body_height:
                continue

            # Row background
            if i == self.selected_index:
                bg = self.selected_background
            elif i == self._hovered_index:
                bg = self.hover_background
            else:
                bg = self.row_background if i % 2 == 0 else self.row_alt_background

            renderer.draw_rect(self.x, ry, self.width, self.row_height, bg)

            # Cell text
            tc = self.selected_text_color if i == self.selected_index else self.text_color

            for j, cell_text in enumerate(row):
                if j >= len(self._col_x):
                    break
                cx = self.x + self._col_x[j]
                cw = self._col_w[j]

                renderer.begin_clip(cx, ry, cw, self.row_height)
                renderer.draw_text(
                    cx + self.cell_padding,
                    ry + self.row_height / 2 + self.font_size / 3,
                    cell_text,
                    tc,
                    self.font_size,
                )
                renderer.end_clip()

        renderer.end_clip()

    # --- Mouse events ---

    def on_mouse_wheel(self, event: MouseWheelEvent) -> bool:
        n = len(self._rows)
        if n == 0:
            return False
        body_height = self.height - self.header_height
        total_content = n * self.row_height
        max_scroll = max(0.0, total_content - body_height)
        if max_scroll <= 0:
            return False
        self._scroll_offset -= event.dy * 30
        self._scroll_offset = max(0.0, min(self._scroll_offset, max_scroll))
        return True

    def on_mouse_move(self, event: MouseEvent):
        if self._resizing:
            delta = event.x - self._resize_start_x
            col = self._columns[self._resize_col_index]
            col.width = max(col.min_width, self._resize_start_width + delta)
            return

        # In header zone — only handle resize cursor detection, no row hover
        if event.y < self.y + self.header_height:
            self._hovered_index = -1
            return

        self._hovered_index = self._index_at(event.y)

    def on_mouse_leave(self):
        self._hovered_index = -1
        self._resizing = False

    def on_mouse_down(self, event: MouseEvent) -> bool:
        # Check for column resize in header
        if event.y < self.y + self.header_height:
            col_idx = self._col_at_border(event.x)
            if col_idx >= 0:
                self._resizing = True
                self._resize_col_index = col_idx
                self._resize_start_x = event.x
                # Use actual computed width, not declared (which is 0 for stretch)
                self._resize_start_width = self._col_w[col_idx] if col_idx < len(self._col_w) else 40.0
                return True
            return False

        idx = self._index_at(event.y)
        if idx < 0:
            return False

        now = time.monotonic()

        # Double-click
        if (idx == self._last_click_index
                and now - self._last_click_time < self._DOUBLE_CLICK_INTERVAL):
            if self.on_activate:
                data = self._row_data[idx] if idx < len(self._row_data) else None
                self.on_activate(idx, data)
            self._last_click_index = -1
            self._last_click_time = 0.0
            return True

        # Single click
        self._last_click_index = idx
        self._last_click_time = now
        self.selected_index = idx
        if self.on_select:
            data = self._row_data[idx] if idx < len(self._row_data) else None
            self.on_select(idx, data)
        return True

    def on_mouse_up(self, event: MouseEvent):
        self._resizing = False
