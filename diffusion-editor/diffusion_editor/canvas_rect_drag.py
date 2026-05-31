"""Small state machine for canvas rectangle drag interactions."""

from __future__ import annotations

from dataclasses import dataclass

from .canvas_geometry import Rect


@dataclass(frozen=True)
class CanvasRectDragResult:
    rect: Rect


class CanvasRectDrag:
    def __init__(self, *, include_end_pixel: bool, min_size: int):
        self._include_end_pixel = include_end_pixel
        self._min_size = min_size
        self._enabled = False
        self._dragging = False
        self._start: tuple[int, int] | None = None
        self._end: tuple[int, int] | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def dragging(self) -> bool:
        return self._dragging

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if not enabled:
            self.cancel_drag()

    def begin(self, x: int, y: int) -> bool:
        if not self._enabled:
            return False
        self._dragging = True
        self._start = (x, y)
        self._end = (x, y)
        return True

    def move(self, x: int, y: int) -> bool:
        if not self._dragging:
            return False
        self._end = (x, y)
        return True

    def finish(self, x: int, y: int) -> CanvasRectDragResult | None:
        if not self._dragging or self._start is None:
            return None
        sx, sy = self._start
        rect = self._normalized_rect(sx, sy, x, y)
        self._enabled = False
        self.cancel_drag()
        x0, y0, x1, y1 = rect
        if x1 - x0 <= self._min_size or y1 - y0 <= self._min_size:
            return None
        return CanvasRectDragResult(rect=rect)

    def cancel_drag(self) -> None:
        self._dragging = False
        self._start = None
        self._end = None

    def preview_rect(self) -> Rect | None:
        if not self._dragging or self._start is None or self._end is None:
            return None
        sx, sy = self._start
        ex, ey = self._end
        return sx, sy, ex, ey

    def _normalized_rect(self, sx: int, sy: int, ex: int, ey: int) -> Rect:
        x0, y0 = min(sx, ex), min(sy, ey)
        x1, y1 = max(sx, ex), max(sy, ey)
        if self._include_end_pixel:
            x1 += 1
            y1 += 1
        return x0, y0, x1, y1
