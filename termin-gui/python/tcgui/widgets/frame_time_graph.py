"""Frame-time bar graph widget."""

from __future__ import annotations

from tcgui.widgets.widget import Widget
from tcgui.widgets.units import px


# Thresholds
_TARGET_60 = 1000.0 / 60.0   # 16.67 ms
_TARGET_30 = 1000.0 / 30.0   # 33.33 ms

# Colors (RGBA 0-1)
_BG = (0.16, 0.16, 0.16, 1.0)
_GRID = (0.24, 0.24, 0.24, 1.0)
_TARGET_LINE = (0.40, 0.40, 0.40, 1.0)
_LABEL = (0.55, 0.55, 0.55, 1.0)
_GREEN = (0.31, 0.71, 0.31, 1.0)
_YELLOW = (0.78, 0.71, 0.31, 1.0)
_RED = (0.78, 0.31, 0.31, 1.0)


class FrameTimeGraph(Widget):
    """Displays a bar chart of recent frame times.

    Usage::

        graph = FrameTimeGraph()
        graph.add_frame(16.5)   # call each frame
    """

    def __init__(self):
        super().__init__()
        self._values: list[float] = []
        self.max_values: int = 120
        self.preferred_height = px(80)

    def add_frame(self, ms: float) -> None:
        self._values.append(ms)
        if len(self._values) > self.max_values:
            self._values.pop(0)

    def clear(self) -> None:
        self._values.clear()

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        w = viewport_w
        if self.preferred_width:
            w = self.preferred_width.to_pixels(viewport_w)
        h = 80.0
        if self.preferred_height:
            h = self.preferred_height.to_pixels(viewport_h)
        return (w, h)

    def render(self, renderer):
        if not self.visible:
            return

        x, y, w, h = self.x, self.y, self.width, self.height

        # Background
        renderer.draw_rect(x, y, w, h, _BG)

        if not self._values:
            renderer.draw_text_centered(
                x + w / 2, y + h / 2,
                "No profiler data", _LABEL, 10,
            )
            return

        max_ms = max(max(self._values), _TARGET_30 + 5.0)

        def ms_to_y(ms: float) -> float:
            return y + h - (ms / max_ms) * h

        # Grid lines at 60 FPS and 30 FPS
        for target in (_TARGET_60, _TARGET_30):
            if target < max_ms:
                ly = ms_to_y(target)
                renderer.draw_line(x, ly, x + w, ly, _GRID, 1.0)

        # Bright target line (60 FPS)
        target_y = ms_to_y(_TARGET_60)
        renderer.draw_line(x, target_y, x + w, target_y, _TARGET_LINE, 1.0)

        # FPS labels
        for target, label in ((_TARGET_60, "60"), (_TARGET_30, "30")):
            if target < max_ms:
                ly = ms_to_y(target)
                renderer.draw_text(x + 2, ly - 2, label, _LABEL, 8)

        # Bars
        n = len(self._values)
        bar_w = w / self.max_values
        bar_gap = max(1.0, bar_w * 0.1)
        actual_bar_w = bar_w - bar_gap

        for i, ms in enumerate(self._values):
            bar_h = (ms / max_ms) * h
            bar_x = x + (self.max_values - n + i) * bar_w
            bar_y = y + h - bar_h

            if ms < _TARGET_60:
                color = _GREEN
            elif ms < _TARGET_30:
                color = _YELLOW
            else:
                color = _RED

            renderer.draw_rect(bar_x, bar_y, actual_bar_w, bar_h, color)
