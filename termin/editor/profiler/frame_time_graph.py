"""Frame time graph widget for profiler panel."""

from __future__ import annotations

from typing import List

from PyQt6 import QtWidgets, QtGui, QtCore


class FrameTimeGraph(QtWidgets.QWidget):
    """
    Мини-график времени кадра.

    Отображает историю frame time в виде вертикальных баров.
    Цвет бара зависит от времени:
    - Зелёный: < 16.67ms (60+ FPS)
    - Жёлтый: < 33.33ms (30+ FPS)
    - Красный: >= 33.33ms (< 30 FPS)
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._values: List[float] = []
        self._max_values = 120
        self._target_ms = 16.67  # 60 FPS target

        self.setMinimumHeight(60)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )

    def add_frame(self, ms: float) -> None:
        """Добавляет время кадра в историю."""
        self._values.append(ms)
        if len(self._values) > self._max_values:
            self._values.pop(0)
        self.update()

    def clear(self) -> None:
        """Очищает историю."""
        self._values.clear()
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """Отрисовка графика."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        # Background
        painter.fillRect(0, 0, w, h, QtGui.QColor(40, 40, 40))

        if not self._values:
            # Текст-подсказка когда нет данных
            painter.setPen(QtGui.QColor(100, 100, 100))
            painter.drawText(
                self.rect(),
                QtCore.Qt.AlignmentFlag.AlignCenter,
                "Enable profiler to see frame times",
            )
            return

        max_ms = max(max(self._values), self._target_ms * 2)

        # Grid lines
        painter.setPen(QtGui.QColor(60, 60, 60))
        for target in [16.67, 33.33, 50.0]:
            if target < max_ms:
                y = h - (target / max_ms) * h
                painter.drawLine(0, int(y), w, int(y))

        # Target line (60 FPS) - более яркая
        target_y = h - (self._target_ms / max_ms) * h
        painter.setPen(QtGui.QColor(100, 100, 100))
        painter.drawLine(0, int(target_y), w, int(target_y))

        # Bars
        bar_w = w / self._max_values
        for i, ms in enumerate(self._values):
            x = i * bar_w
            bar_h = (ms / max_ms) * h
            y = h - bar_h

            # Color based on frame time
            if ms < 16.67:
                color = QtGui.QColor(80, 180, 80)  # Green - 60+ FPS
            elif ms < 33.33:
                color = QtGui.QColor(200, 180, 80)  # Yellow - 30+ FPS
            else:
                color = QtGui.QColor(200, 80, 80)  # Red - < 30 FPS

            painter.fillRect(
                int(x), int(y), max(1, int(bar_w) - 1), int(bar_h), color
            )

        # Labels
        painter.setPen(QtGui.QColor(150, 150, 150))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)

        # 60 FPS label
        if self._target_ms < max_ms:
            painter.drawText(5, int(target_y) - 2, "60")

        # 30 FPS label
        target_30 = 33.33
        if target_30 < max_ms:
            y_30 = h - (target_30 / max_ms) * h
            painter.drawText(5, int(y_30) - 2, "30")
