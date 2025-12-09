# ===== termin/editor/color_dialog.py =====
"""
Кастомный ColorDialog в стиле Unity.
Работает в диапазоне 0-1 для RGB.

Структура интерфейса:
┌─────────────────────────────────────────────────────┐
│  [Квадрат SV (Saturation-Value)]  [Полоса Hue]     │
│                                                     │
│  R: [=====0.50=====]  0.50                         │
│  G: [=====0.75=====]  0.75                         │
│  B: [=====0.25=====]  0.25                         │
│  A: [=====1.00=====]  1.00                         │
│                                                     │
│  Hex: #FF00FF                                       │
│                                                     │
│  [Old Color] [New Color]                            │
│                                                     │
│         [OK]     [Cancel]                           │
└─────────────────────────────────────────────────────┘
"""
from __future__ import annotations

from typing import Optional, Tuple

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QLineEdit,
    QPushButton,
    QWidget,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
)
from PyQt6.QtGui import (
    QColor,
    QPainter,
    QLinearGradient,
    QImage,
    QPixmap,
    QPen,
    QBrush,
    QMouseEvent,
    QPaintEvent,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRect, QSize


class HueStrip(QWidget):
    """
    Вертикальная полоса для выбора Hue (0-360).
    Hue меняется по вертикали сверху вниз: 0 → 360.
    """

    hue_changed = pyqtSignal(float)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._hue = 0.0  # 0..1 (соответствует 0..360 градусов)
        self.setFixedWidth(24)
        self.setMinimumHeight(150)
        self._image: Optional[QImage] = None

    def set_hue(self, hue: float) -> None:
        """Установить hue в диапазоне 0..1."""
        self._hue = max(0.0, min(1.0, hue))
        self.update()

    def hue(self) -> float:
        return self._hue

    def _build_image(self) -> QImage:
        """Построить изображение радужной полосы Hue."""
        h = self.height()
        w = self.width()
        if h <= 0 or w <= 0:
            return QImage()

        image = QImage(w, h, QImage.Format.Format_RGB32)
        for y in range(h):
            # Hue от 0 (top) до 1 (bottom)
            hue_value = y / max(h - 1, 1)
            color = QColor.fromHsvF(hue_value, 1.0, 1.0)
            rgb = color.rgb()
            for x in range(w):
                image.setPixel(x, y, rgb)
        return image

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Рисуем полосу Hue
        if self._image is None or self._image.size() != self.size():
            self._image = self._build_image()

        painter.drawImage(0, 0, self._image)

        # Рисуем маркер текущего Hue
        y = int(self._hue * (self.height() - 1))
        marker_rect = QRect(0, y - 2, self.width(), 4)
        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        painter.drawRect(marker_rect)
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.drawRect(marker_rect.adjusted(1, 1, -1, -1))

        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._update_hue_from_pos(event.pos())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self._update_hue_from_pos(event.pos())

    def _update_hue_from_pos(self, pos: QPoint) -> None:
        h = self.height()
        if h <= 1:
            return
        hue = pos.y() / (h - 1)
        hue = max(0.0, min(1.0, hue))
        if abs(hue - self._hue) > 0.001:
            self._hue = hue
            self.update()
            self.hue_changed.emit(self._hue)


class SVSquare(QWidget):
    """
    Квадрат Saturation-Value для заданного Hue.
    По горизонтали: Saturation (0 слева, 1 справа).
    По вертикали: Value (1 сверху, 0 снизу).
    """

    sv_changed = pyqtSignal(float, float)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._hue = 0.0  # 0..1
        self._saturation = 1.0  # 0..1
        self._value = 1.0  # 0..1
        self.setMinimumSize(150, 150)
        self._image: Optional[QImage] = None
        self._cached_hue: Optional[float] = None

    def set_hsv(self, h: float, s: float, v: float) -> None:
        """Установить HSV (все в диапазоне 0..1)."""
        self._hue = max(0.0, min(1.0, h))
        self._saturation = max(0.0, min(1.0, s))
        self._value = max(0.0, min(1.0, v))
        self.update()

    def set_hue(self, hue: float) -> None:
        """Установить только Hue, сбрасывая кэш изображения."""
        self._hue = max(0.0, min(1.0, hue))
        self.update()

    def saturation(self) -> float:
        return self._saturation

    def value(self) -> float:
        return self._value

    def _build_image(self, hue: float) -> QImage:
        """Построить изображение SV-квадрата для данного Hue."""
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return QImage()

        image = QImage(w, h, QImage.Format.Format_RGB32)
        for y in range(h):
            # Value: 1 сверху, 0 снизу
            val = 1.0 - (y / max(h - 1, 1))
            for x in range(w):
                # Saturation: 0 слева, 1 справа
                sat = x / max(w - 1, 1)
                color = QColor.fromHsvF(hue, sat, val)
                image.setPixel(x, y, color.rgb())
        return image

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Перестраиваем изображение, если Hue изменился
        if self._image is None or self._cached_hue != self._hue or self._image.size() != self.size():
            self._image = self._build_image(self._hue)
            self._cached_hue = self._hue

        painter.drawImage(0, 0, self._image)

        # Рисуем маркер текущего S,V
        w = self.width()
        h = self.height()
        cx = int(self._saturation * (w - 1))
        cy = int((1.0 - self._value) * (h - 1))

        # Круглый маркер
        radius = 6
        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPoint(cx, cy), radius, radius)
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.drawEllipse(QPoint(cx, cy), radius - 1, radius - 1)

        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._update_sv_from_pos(event.pos())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self._update_sv_from_pos(event.pos())

    def _update_sv_from_pos(self, pos: QPoint) -> None:
        w = self.width()
        h = self.height()
        if w <= 1 or h <= 1:
            return

        sat = pos.x() / (w - 1)
        val = 1.0 - pos.y() / (h - 1)
        sat = max(0.0, min(1.0, sat))
        val = max(0.0, min(1.0, val))

        if abs(sat - self._saturation) > 0.001 or abs(val - self._value) > 0.001:
            self._saturation = sat
            self._value = val
            self.update()
            self.sv_changed.emit(self._saturation, self._value)


class ColorPreview(QWidget):
    """
    Виджет превью цвета (старый + новый).
    Рисует шахматный фон для отображения прозрачности.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._old_color = QColor(255, 255, 255, 255)
        self._new_color = QColor(255, 255, 255, 255)
        self.setFixedHeight(40)
        self.setMinimumWidth(100)

    def set_old_color(self, color: QColor) -> None:
        self._old_color = color
        self.update()

    def set_new_color(self, color: QColor) -> None:
        self._new_color = color
        self.update()

    def _draw_checker_pattern(self, painter: QPainter, rect: QRect) -> None:
        """Рисует шахматный паттерн для визуализации прозрачности."""
        checker_size = 8
        light = QColor(200, 200, 200)
        dark = QColor(128, 128, 128)

        for y in range(rect.top(), rect.bottom(), checker_size):
            for x in range(rect.left(), rect.right(), checker_size):
                is_light = ((x - rect.left()) // checker_size + (y - rect.top()) // checker_size) % 2 == 0
                color = light if is_light else dark
                cell_rect = QRect(
                    x, y,
                    min(checker_size, rect.right() - x),
                    min(checker_size, rect.bottom() - y)
                )
                painter.fillRect(cell_rect, color)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        w = self.width()
        h = self.height()

        left_rect = QRect(0, 0, w // 2, h)
        right_rect = QRect(w // 2, 0, w - w // 2, h)

        # Рисуем шахматный фон для прозрачности
        self._draw_checker_pattern(painter, left_rect)
        self._draw_checker_pattern(painter, right_rect)

        # Левая половина — старый цвет
        painter.fillRect(left_rect, self._old_color)
        # Правая половина — новый цвет
        painter.fillRect(right_rect, self._new_color)

        # Рамка
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.drawRect(0, 0, w - 1, h - 1)
        painter.drawLine(w // 2, 0, w // 2, h)

        # Подписи
        painter.setPen(Qt.GlobalColor.black if self._old_color.lightnessF() > 0.5 else Qt.GlobalColor.white)
        painter.drawText(QRect(0, 0, w // 2, h), Qt.AlignmentFlag.AlignCenter, "Old")
        painter.setPen(Qt.GlobalColor.black if self._new_color.lightnessF() > 0.5 else Qt.GlobalColor.white)
        painter.drawText(QRect(w // 2, 0, w - w // 2, h), Qt.AlignmentFlag.AlignCenter, "New")

        painter.end()


class ColorDialog(QDialog):
    """
    Диалог выбора цвета в стиле Unity.
    Работает в диапазоне RGBA 0..1.

    Использование:
        dlg = ColorDialog(initial_color=(0.5, 0.2, 0.8, 1.0), parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            r, g, b, a = dlg.get_color_01()
    """

    color_changed = pyqtSignal()

    def __init__(
        self,
        initial_color: Tuple[float, ...] = (1.0, 1.0, 1.0, 1.0),
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Color Picker")
        self.setMinimumSize(350, 450)

        # Сохраняем исходный цвет (0..1)
        self._old_r = float(initial_color[0]) if len(initial_color) > 0 else 1.0
        self._old_g = float(initial_color[1]) if len(initial_color) > 1 else 1.0
        self._old_b = float(initial_color[2]) if len(initial_color) > 2 else 1.0
        self._old_a = float(initial_color[3]) if len(initial_color) > 3 else 1.0

        # Текущий цвет (0..1)
        self._r = self._old_r
        self._g = self._old_g
        self._b = self._old_b
        self._a = self._old_a

        self._updating = False  # флаг для предотвращения рекурсии

        self._setup_ui()
        self._sync_from_rgb()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # === Верхняя часть: SV-квадрат + Hue-полоса ===
        picker_layout = QHBoxLayout()
        picker_layout.setSpacing(8)

        self._sv_square = SVSquare()
        self._hue_strip = HueStrip()

        picker_layout.addWidget(self._sv_square, 1)
        picker_layout.addWidget(self._hue_strip)
        layout.addLayout(picker_layout)

        # === RGBA слайдеры (0..1) ===
        rgba_layout = QGridLayout()
        rgba_layout.setSpacing(4)

        # R
        rgba_layout.addWidget(QLabel("R:"), 0, 0)
        self._r_slider = QSlider(Qt.Orientation.Horizontal)
        self._r_slider.setRange(0, 1000)
        rgba_layout.addWidget(self._r_slider, 0, 1)
        self._r_spin = QDoubleSpinBox()
        self._r_spin.setRange(0.0, 1.0)
        self._r_spin.setDecimals(3)
        self._r_spin.setSingleStep(0.01)
        self._r_spin.setFixedWidth(70)
        rgba_layout.addWidget(self._r_spin, 0, 2)

        # G
        rgba_layout.addWidget(QLabel("G:"), 1, 0)
        self._g_slider = QSlider(Qt.Orientation.Horizontal)
        self._g_slider.setRange(0, 1000)
        rgba_layout.addWidget(self._g_slider, 1, 1)
        self._g_spin = QDoubleSpinBox()
        self._g_spin.setRange(0.0, 1.0)
        self._g_spin.setDecimals(3)
        self._g_spin.setSingleStep(0.01)
        self._g_spin.setFixedWidth(70)
        rgba_layout.addWidget(self._g_spin, 1, 2)

        # B
        rgba_layout.addWidget(QLabel("B:"), 2, 0)
        self._b_slider = QSlider(Qt.Orientation.Horizontal)
        self._b_slider.setRange(0, 1000)
        rgba_layout.addWidget(self._b_slider, 2, 1)
        self._b_spin = QDoubleSpinBox()
        self._b_spin.setRange(0.0, 1.0)
        self._b_spin.setDecimals(3)
        self._b_spin.setSingleStep(0.01)
        self._b_spin.setFixedWidth(70)
        rgba_layout.addWidget(self._b_spin, 2, 2)

        # A (Alpha)
        rgba_layout.addWidget(QLabel("A:"), 3, 0)
        self._a_slider = QSlider(Qt.Orientation.Horizontal)
        self._a_slider.setRange(0, 1000)
        rgba_layout.addWidget(self._a_slider, 3, 1)
        self._a_spin = QDoubleSpinBox()
        self._a_spin.setRange(0.0, 1.0)
        self._a_spin.setDecimals(3)
        self._a_spin.setSingleStep(0.01)
        self._a_spin.setFixedWidth(70)
        rgba_layout.addWidget(self._a_spin, 3, 2)

        layout.addLayout(rgba_layout)

        # === Hex (поддерживает RRGGBB и RRGGBBAA) ===
        hex_layout = QHBoxLayout()
        hex_layout.addWidget(QLabel("Hex:"))
        self._hex_edit = QLineEdit()
        self._hex_edit.setFixedWidth(100)
        self._hex_edit.setMaxLength(9)  # #RRGGBBAA
        hex_layout.addWidget(self._hex_edit)
        hex_layout.addStretch()
        layout.addLayout(hex_layout)

        # === Превью ===
        self._preview = ColorPreview()
        layout.addWidget(self._preview)

        # === Кнопки ===
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        cancel_btn = QPushButton("Cancel")
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        # === Коннекты ===
        self._sv_square.sv_changed.connect(self._on_sv_changed)
        self._hue_strip.hue_changed.connect(self._on_hue_changed)

        self._r_slider.valueChanged.connect(self._on_r_slider_changed)
        self._g_slider.valueChanged.connect(self._on_g_slider_changed)
        self._b_slider.valueChanged.connect(self._on_b_slider_changed)
        self._a_slider.valueChanged.connect(self._on_a_slider_changed)

        self._r_spin.valueChanged.connect(self._on_r_spin_changed)
        self._g_spin.valueChanged.connect(self._on_g_spin_changed)
        self._b_spin.valueChanged.connect(self._on_b_spin_changed)
        self._a_spin.valueChanged.connect(self._on_a_spin_changed)

        self._hex_edit.editingFinished.connect(self._on_hex_edited)

        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

        # Инициализация превью
        old_qcolor = QColor.fromRgbF(self._old_r, self._old_g, self._old_b, self._old_a)
        self._preview.set_old_color(old_qcolor)
        self._preview.set_new_color(old_qcolor)

    def _sync_from_rgb(self) -> None:
        """Синхронизировать все виджеты из текущего RGBA."""
        if self._updating:
            return
        self._updating = True

        # Преобразуем RGB → HSV
        qcolor = QColor.fromRgbF(self._r, self._g, self._b)
        h = qcolor.hueF()
        s = qcolor.saturationF()
        v = qcolor.valueF()

        # Если hue = -1 (серый цвет), сохраняем предыдущий hue
        if h < 0:
            h = self._hue_strip.hue()

        self._hue_strip.set_hue(h)
        self._sv_square.set_hsv(h, s, v)

        # Слайдеры RGB
        self._r_slider.setValue(int(self._r * 1000))
        self._g_slider.setValue(int(self._g * 1000))
        self._b_slider.setValue(int(self._b * 1000))
        self._a_slider.setValue(int(self._a * 1000))

        # Спинбоксы
        self._r_spin.setValue(self._r)
        self._g_spin.setValue(self._g)
        self._b_spin.setValue(self._b)
        self._a_spin.setValue(self._a)

        # Hex с альфой
        hex_str = "#{:02X}{:02X}{:02X}{:02X}".format(
            int(self._r * 255),
            int(self._g * 255),
            int(self._b * 255),
            int(self._a * 255),
        )
        self._hex_edit.setText(hex_str)

        # Превью с альфой
        qcolor_with_alpha = QColor.fromRgbF(self._r, self._g, self._b, self._a)
        self._preview.set_new_color(qcolor_with_alpha)

        self._updating = False

    def _sync_from_hsv(self) -> None:
        """Синхронизировать RGB из HSV (hue_strip + sv_square), сохраняя альфу."""
        if self._updating:
            return
        self._updating = True

        h = self._hue_strip.hue()
        s = self._sv_square.saturation()
        v = self._sv_square.value()

        qcolor = QColor.fromHsvF(h, s, v)
        self._r = qcolor.redF()
        self._g = qcolor.greenF()
        self._b = qcolor.blueF()
        # _a остаётся без изменений

        # Слайдеры
        self._r_slider.setValue(int(self._r * 1000))
        self._g_slider.setValue(int(self._g * 1000))
        self._b_slider.setValue(int(self._b * 1000))

        # Спинбоксы
        self._r_spin.setValue(self._r)
        self._g_spin.setValue(self._g)
        self._b_spin.setValue(self._b)

        # Hex с альфой
        hex_str = "#{:02X}{:02X}{:02X}{:02X}".format(
            int(self._r * 255),
            int(self._g * 255),
            int(self._b * 255),
            int(self._a * 255),
        )
        self._hex_edit.setText(hex_str)

        # Превью с альфой
        qcolor_with_alpha = QColor.fromRgbF(self._r, self._g, self._b, self._a)
        self._preview.set_new_color(qcolor_with_alpha)

        self._updating = False
        self.color_changed.emit()

    def _on_sv_changed(self, s: float, v: float) -> None:
        self._sv_square.set_hsv(self._hue_strip.hue(), s, v)
        self._sync_from_hsv()

    def _on_hue_changed(self, hue: float) -> None:
        self._sv_square.set_hue(hue)
        self._sync_from_hsv()

    def _on_r_slider_changed(self, val: int) -> None:
        if self._updating:
            return
        self._r = val / 1000.0
        self._sync_from_rgb()
        self.color_changed.emit()

    def _on_g_slider_changed(self, val: int) -> None:
        if self._updating:
            return
        self._g = val / 1000.0
        self._sync_from_rgb()
        self.color_changed.emit()

    def _on_b_slider_changed(self, val: int) -> None:
        if self._updating:
            return
        self._b = val / 1000.0
        self._sync_from_rgb()
        self.color_changed.emit()

    def _on_a_slider_changed(self, val: int) -> None:
        if self._updating:
            return
        self._a = val / 1000.0
        self._sync_from_rgb()
        self.color_changed.emit()

    def _on_r_spin_changed(self, val: float) -> None:
        if self._updating:
            return
        self._r = val
        self._sync_from_rgb()
        self.color_changed.emit()

    def _on_g_spin_changed(self, val: float) -> None:
        if self._updating:
            return
        self._g = val
        self._sync_from_rgb()
        self.color_changed.emit()

    def _on_b_spin_changed(self, val: float) -> None:
        if self._updating:
            return
        self._b = val
        self._sync_from_rgb()
        self.color_changed.emit()

    def _on_a_spin_changed(self, val: float) -> None:
        if self._updating:
            return
        self._a = val
        self._sync_from_rgb()
        self.color_changed.emit()

    def _on_hex_edited(self) -> None:
        """
        Парсит hex-строку.
        Поддерживает форматы: #RRGGBB, #RRGGBBAA, RRGGBB, RRGGBBAA
        """
        if self._updating:
            return
        text = self._hex_edit.text().strip()
        if text.startswith("#"):
            text = text[1:]

        if len(text) == 6:
            # #RRGGBB — альфа = 1.0
            try:
                r_int = int(text[0:2], 16)
                g_int = int(text[2:4], 16)
                b_int = int(text[4:6], 16)
            except ValueError:
                return
            self._r = r_int / 255.0
            self._g = g_int / 255.0
            self._b = b_int / 255.0
            # _a остаётся без изменений
        elif len(text) == 8:
            # #RRGGBBAA
            try:
                r_int = int(text[0:2], 16)
                g_int = int(text[2:4], 16)
                b_int = int(text[4:6], 16)
                a_int = int(text[6:8], 16)
            except ValueError:
                return
            self._r = r_int / 255.0
            self._g = g_int / 255.0
            self._b = b_int / 255.0
            self._a = a_int / 255.0
        else:
            return

        self._sync_from_rgb()
        self.color_changed.emit()

    def get_color_01(self) -> Tuple[float, float, float, float]:
        """Получить текущий цвет RGBA в диапазоне 0..1."""
        return (self._r, self._g, self._b, self._a)

    def get_color_255(self) -> Tuple[int, int, int, int]:
        """Получить текущий цвет RGBA в диапазоне 0..255."""
        return (
            int(self._r * 255),
            int(self._g * 255),
            int(self._b * 255),
            int(self._a * 255),
        )

    def get_qcolor(self) -> QColor:
        """Получить текущий цвет как QColor."""
        return QColor.fromRgbF(self._r, self._g, self._b, self._a)

    @staticmethod
    def get_color(
        initial: Tuple[float, ...] = (1.0, 1.0, 1.0, 1.0),
        parent: Optional[QWidget] = None,
    ) -> Optional[Tuple[float, float, float, float]]:
        """
        Статический метод для вызова диалога.
        Возвращает кортеж (r, g, b, a) в диапазоне 0..1 или None при отмене.
        """
        dlg = ColorDialog(initial, parent)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return dlg.get_color_01()
        return None
