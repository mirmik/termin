"""
Vec3ListWidget — виджет для редактирования массива 3D точек.

Используется в инспекторе для LineRenderer.points и аналогичных полей.
"""

from __future__ import annotations

from typing import List, Tuple, Optional, Callable

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QDoubleSpinBox,
    QLabel,
    QFrame,
)
from PyQt6.QtCore import pyqtSignal, Qt


class Vec3ListWidget(QWidget):
    """
    Виджет для редактирования списка 3D точек.

    Состоит из:
    - Списка точек (QListWidget)
    - Кнопок добавления/удаления
    - Редактора выбранной точки (3 spinbox для x, y, z)

    Signals:
        value_changed: Испускается при изменении списка точек.
    """

    value_changed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._points: List[Tuple[float, float, float]] = []
        self._updating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Список точек
        self._list = QListWidget()
        self._list.setMaximumHeight(120)
        self._list.currentRowChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list)

        # Кнопки управления
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(4)

        self._add_btn = QPushButton("+")
        self._add_btn.setFixedSize(24, 24)
        self._add_btn.setToolTip("Add point")
        self._add_btn.clicked.connect(self._add_point)
        btn_layout.addWidget(self._add_btn)

        self._remove_btn = QPushButton("-")
        self._remove_btn.setFixedSize(24, 24)
        self._remove_btn.setToolTip("Remove point")
        self._remove_btn.clicked.connect(self._remove_point)
        btn_layout.addWidget(self._remove_btn)

        self._move_up_btn = QPushButton("\u2191")
        self._move_up_btn.setFixedSize(24, 24)
        self._move_up_btn.setToolTip("Move up")
        self._move_up_btn.clicked.connect(self._move_up)
        btn_layout.addWidget(self._move_up_btn)

        self._move_down_btn = QPushButton("\u2193")
        self._move_down_btn.setFixedSize(24, 24)
        self._move_down_btn.setToolTip("Move down")
        self._move_down_btn.clicked.connect(self._move_down)
        btn_layout.addWidget(self._move_down_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Редактор выбранной точки
        editor_frame = QFrame()
        editor_frame.setFrameShape(QFrame.Shape.StyledPanel)
        editor_layout = QHBoxLayout(editor_frame)
        editor_layout.setContentsMargins(4, 4, 4, 4)
        editor_layout.setSpacing(4)

        self._spinboxes: List[QDoubleSpinBox] = []
        for axis in ("X", "Y", "Z"):
            label = QLabel(axis)
            label.setFixedWidth(12)
            editor_layout.addWidget(label)

            sb = QDoubleSpinBox()
            sb.setDecimals(3)
            sb.setRange(-1e6, 1e6)
            sb.setSingleStep(0.1)
            sb.valueChanged.connect(self._on_spinbox_changed)
            editor_layout.addWidget(sb)
            self._spinboxes.append(sb)

        layout.addWidget(editor_frame)
        self._editor_frame = editor_frame

        self._update_buttons()

    def get_value(self) -> List[Tuple[float, float, float]]:
        """Возвращает текущий список точек."""
        return list(self._points)

    def set_value(self, points: List[Tuple[float, float, float]]):
        """Устанавливает список точек."""
        self._updating = True
        try:
            self._points = [tuple(p) for p in points] if points else []
            self._rebuild_list()
            self._update_buttons()
        finally:
            self._updating = False

    def _rebuild_list(self):
        """Перестраивает QListWidget из текущих точек."""
        current_row = self._list.currentRow()
        self._list.clear()

        for i, p in enumerate(self._points):
            text = f"{i}: ({p[0]:.2f}, {p[1]:.2f}, {p[2]:.2f})"
            item = QListWidgetItem(text)
            self._list.addItem(item)

        if 0 <= current_row < len(self._points):
            self._list.setCurrentRow(current_row)
        elif self._points:
            self._list.setCurrentRow(len(self._points) - 1)

    def _update_buttons(self):
        """Обновляет состояние кнопок."""
        has_selection = self._list.currentRow() >= 0
        self._remove_btn.setEnabled(has_selection)
        self._move_up_btn.setEnabled(has_selection and self._list.currentRow() > 0)
        self._move_down_btn.setEnabled(
            has_selection and self._list.currentRow() < len(self._points) - 1
        )
        self._editor_frame.setEnabled(has_selection)

    def _on_selection_changed(self, row: int):
        """Обрабатывает изменение выбранной точки."""
        self._update_buttons()

        if row < 0 or row >= len(self._points):
            return

        self._updating = True
        try:
            p = self._points[row]
            for i, sb in enumerate(self._spinboxes):
                sb.setValue(p[i])
        finally:
            self._updating = False

    def _on_spinbox_changed(self):
        """Обрабатывает изменение значения в spinbox."""
        if self._updating:
            return

        row = self._list.currentRow()
        if row < 0 or row >= len(self._points):
            return

        new_point = tuple(sb.value() for sb in self._spinboxes)
        self._points[row] = new_point

        # Обновляем текст в списке
        item = self._list.item(row)
        if item:
            p = new_point
            item.setText(f"{row}: ({p[0]:.2f}, {p[1]:.2f}, {p[2]:.2f})")

        self.value_changed.emit()

    def _add_point(self):
        """Добавляет новую точку."""
        # Если есть выбранная точка, добавляем после неё со смещением
        row = self._list.currentRow()
        if row >= 0 and row < len(self._points):
            base = self._points[row]
            new_point = (base[0] + 1.0, base[1], base[2])
            insert_pos = row + 1
        else:
            # Иначе добавляем в конец
            if self._points:
                base = self._points[-1]
                new_point = (base[0] + 1.0, base[1], base[2])
            else:
                new_point = (0.0, 0.0, 0.0)
            insert_pos = len(self._points)

        self._points.insert(insert_pos, new_point)
        self._rebuild_list()
        self._list.setCurrentRow(insert_pos)
        self._update_buttons()
        self.value_changed.emit()

    def _remove_point(self):
        """Удаляет выбранную точку."""
        row = self._list.currentRow()
        if row < 0 or row >= len(self._points):
            return

        del self._points[row]
        self._rebuild_list()
        self._update_buttons()
        self.value_changed.emit()

    def _move_up(self):
        """Перемещает выбранную точку вверх."""
        row = self._list.currentRow()
        if row <= 0 or row >= len(self._points):
            return

        self._points[row], self._points[row - 1] = (
            self._points[row - 1],
            self._points[row],
        )
        self._rebuild_list()
        self._list.setCurrentRow(row - 1)
        self._update_buttons()
        self.value_changed.emit()

    def _move_down(self):
        """Перемещает выбранную точку вниз."""
        row = self._list.currentRow()
        if row < 0 or row >= len(self._points) - 1:
            return

        self._points[row], self._points[row + 1] = (
            self._points[row + 1],
            self._points[row],
        )
        self._rebuild_list()
        self._list.setCurrentRow(row + 1)
        self._update_buttons()
        self.value_changed.emit()
