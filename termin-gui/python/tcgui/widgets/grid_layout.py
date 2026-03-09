"""GridLayout container."""

from __future__ import annotations

from dataclasses import dataclass

from tcgui.widgets.widget import Widget


@dataclass
class _GridItem:
    widget: Widget
    row: int
    col: int
    row_span: int
    col_span: int


class GridLayout(Widget):
    """Grid container with explicit row/column placement."""

    def __init__(self, columns: int = 2):
        super().__init__()
        self.columns = max(1, columns)
        self.row_spacing: float = 4.0
        self.column_spacing: float = 4.0
        self.padding: float = 0.0
        self._items: list[_GridItem] = []
        self._column_stretch: dict[int, float] = {}
        self._row_stretch: dict[int, float] = {}

    def add(self, child: Widget, row: int, col: int, row_span: int = 1, col_span: int = 1) -> Widget:
        """Add a child at grid cell position."""
        row = max(0, row)
        col = max(0, col)
        row_span = max(1, row_span)
        col_span = max(1, col_span)
        if col >= self.columns:
            raise ValueError(f"GridLayout col {col} out of range for {self.columns} columns")
        if col + col_span > self.columns:
            raise ValueError("GridLayout col span exceeds column count")
        self._items.append(_GridItem(child, row, col, row_span, col_span))
        super().add_child(child)
        return child

    def remove_child(self, child: Widget):
        self._items = [it for it in self._items if it.widget is not child]
        super().remove_child(child)

    def clear(self) -> None:
        for child in self.children[:]:
            self.remove_child(child)

    def set_column_stretch(self, column: int, stretch: float) -> None:
        if stretch <= 0:
            self._column_stretch.pop(column, None)
            return
        self._column_stretch[column] = stretch

    def set_row_stretch(self, row: int, stretch: float) -> None:
        if stretch <= 0:
            self._row_stretch.pop(row, None)
            return
        self._row_stretch[row] = stretch

    def _row_count(self) -> int:
        if not self._items:
            return 0
        return max(it.row + it.row_span for it in self._items)

    def _measure(self, viewport_w: float, viewport_h: float) -> tuple[list[float], list[float]]:
        cols = self.columns
        rows = self._row_count()
        col_widths = [0.0] * cols
        row_heights = [0.0] * rows

        for it in self._items:
            if not it.widget.visible:
                continue
            cw, ch = it.widget.compute_size(viewport_w, viewport_h)
            if it.col_span == 1:
                col_widths[it.col] = max(col_widths[it.col], cw)
            if it.row_span == 1:
                row_heights[it.row] = max(row_heights[it.row], ch)

        for it in self._items:
            if not it.widget.visible:
                continue
            cw, ch = it.widget.compute_size(viewport_w, viewport_h)
            if it.col_span > 1:
                start = it.col
                end = it.col + it.col_span
                current = sum(col_widths[start:end]) + self.column_spacing * (it.col_span - 1)
                if current < cw:
                    extra = (cw - current) / it.col_span
                    for c in range(start, end):
                        col_widths[c] += extra
            if it.row_span > 1:
                start = it.row
                end = it.row + it.row_span
                current = sum(row_heights[start:end]) + self.row_spacing * (it.row_span - 1)
                if current < ch:
                    extra = (ch - current) / it.row_span
                    for r in range(start, end):
                        row_heights[r] += extra

        return col_widths, row_heights

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h),
            )

        col_widths, row_heights = self._measure(viewport_w, viewport_h)
        cols = len(col_widths)
        rows = len(row_heights)
        width = sum(col_widths) + max(0, cols - 1) * self.column_spacing + self.padding * 2
        height = sum(row_heights) + max(0, rows - 1) * self.row_spacing + self.padding * 2

        if self.preferred_width:
            width = self.preferred_width.to_pixels(viewport_w)
        if self.preferred_height:
            height = self.preferred_height.to_pixels(viewport_h)
        return (width, height)

    def _distribute_extra(self, sizes: list[float], extra: float, stretch_map: dict[int, float]) -> None:
        if extra <= 0 or not sizes:
            return
        weight_sum = 0.0
        for i in range(len(sizes)):
            weight_sum += stretch_map.get(i, 0.0)
        if weight_sum <= 0:
            sizes[-1] += extra
            return
        for i in range(len(sizes)):
            w = stretch_map.get(i, 0.0)
            if w > 0:
                sizes[i] += extra * (w / weight_sum)

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float):
        super().layout(x, y, width, height, viewport_w, viewport_h)
        col_widths, row_heights = self._measure(viewport_w, viewport_h)
        if not col_widths and not row_heights:
            return

        content_w = width - self.padding * 2
        content_h = height - self.padding * 2
        base_w = sum(col_widths) + max(0, len(col_widths) - 1) * self.column_spacing
        base_h = sum(row_heights) + max(0, len(row_heights) - 1) * self.row_spacing
        self._distribute_extra(col_widths, max(0.0, content_w - base_w), self._column_stretch)
        self._distribute_extra(row_heights, max(0.0, content_h - base_h), self._row_stretch)

        col_x = [x + self.padding]
        for i in range(1, len(col_widths)):
            col_x.append(col_x[-1] + col_widths[i - 1] + self.column_spacing)
        row_y = [y + self.padding]
        for i in range(1, len(row_heights)):
            row_y.append(row_y[-1] + row_heights[i - 1] + self.row_spacing)

        for it in self._items:
            if not it.widget.visible:
                continue
            if it.row >= len(row_heights) or it.col >= len(col_widths):
                continue
            child_x = col_x[it.col]
            child_y = row_y[it.row]
            child_w = sum(col_widths[it.col:it.col + it.col_span]) + self.column_spacing * (it.col_span - 1)
            child_h = sum(row_heights[it.row:it.row + it.row_span]) + self.row_spacing * (it.row_span - 1)
            it.widget.layout(child_x, child_y, max(1.0, child_w), max(1.0, child_h), viewport_w, viewport_h)
