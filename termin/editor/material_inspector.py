# ===== termin/editor/material_inspector.py =====
"""
Инспектор материалов для редактора.

Позволяет:
- Выбирать шейдер из загруженных .shader файлов
- Редактировать все @property из шейдера
- Сохранять/загружать материалы из .material файлов
- Поддерживает типы: Float, Int, Bool, Vec2, Vec3, Vec4, Color, Texture

Формат .material файла:
{
    "shader": "path/to/shader.shader",
    "uniforms": {
        "u_color": [1.0, 0.5, 0.0, 1.0],
        "u_roughness": 0.5
    },
    "textures": {
        "u_mainTex": "path/to/texture.png"
    }
}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QDoubleSpinBox,
    QSpinBox,
    QCheckBox,
    QComboBox,
    QPushButton,
    QLineEdit,
    QScrollArea,
    QFrame,
    QFileDialog,
    QGroupBox,
    QMessageBox,
    QDialog,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QImage, QPixmap

from termin.editor.color_dialog import ColorDialog
from termin.visualization.core.material import Material
from termin.geombase import Vec4
from termin.visualization.render.shader_parser import (
    ShaderMultyPhaseProgramm,
    MaterialProperty,
)


class ColorButton(QPushButton):
    """Кнопка для выбора цвета с превью."""

    color_changed = pyqtSignal(object)  # Vec4
    editing_finished = pyqtSignal()

    def __init__(self, color: Vec4 | tuple = (1.0, 1.0, 1.0, 1.0), parent: QWidget | None = None):
        super().__init__(parent)
        self._color = self._to_vec4(color)
        self._original_color: Vec4 | None = None
        self._dialog: ColorDialog | None = None
        self.setFixedSize(60, 24)
        self._update_style()
        self.clicked.connect(self._on_clicked)

    def _to_vec4(self, color: Vec4 | tuple) -> Vec4:
        if isinstance(color, Vec4):
            return color
        return Vec4(color[0], color[1], color[2], color[3])

    def set_color(self, color: Vec4 | tuple) -> None:
        self._color = self._to_vec4(color)
        self._update_style()

    def get_color(self) -> Vec4:
        return self._color

    def _update_style(self) -> None:
        r255 = int(self._color.x * 255)
        g255 = int(self._color.y * 255)
        b255 = int(self._color.z * 255)
        a255 = int(self._color.w * 255)
        self.setStyleSheet(
            f"background-color: rgba({r255}, {g255}, {b255}, {a255}); "
            f"border: 1px solid #555;"
        )

    def _on_clicked(self) -> None:
        # Сохраняем исходный цвет для возможного отката
        self._original_color = Vec4(self._color.x, self._color.y, self._color.z, self._color.w)

        # Non-modal диалог чтобы не блокировать рендер
        self._dialog = ColorDialog((self._color.x, self._color.y, self._color.z, self._color.w), self)
        self._dialog.color_changed.connect(self._on_dialog_color_changed)
        self._dialog.accepted.connect(self._on_dialog_accepted)
        self._dialog.rejected.connect(self._on_dialog_rejected)
        self._dialog.show()

    def _on_dialog_color_changed(self) -> None:
        """Live preview - обновляем цвет без сохранения."""
        if self._dialog is not None:
            t = self._dialog.get_color_01()
            self._color = Vec4(t[0], t[1], t[2], t[3])
            self._update_style()
            self.color_changed.emit(self._color)

    def _on_dialog_accepted(self) -> None:
        """OK - сохраняем в файл."""
        self._dialog = None
        self._original_color = None
        self.editing_finished.emit()

    def _on_dialog_rejected(self) -> None:
        """Cancel - откатываем на исходный цвет."""
        if self._original_color is not None:
            self._color = self._original_color
            self._update_style()
            self.color_changed.emit(self._color)
        self._dialog = None
        self._original_color = None


class Vec2Editor(QWidget):
    """Редактор для vec2."""

    value_changed = pyqtSignal(tuple)
    editing_finished = pyqtSignal()

    def __init__(self, value: tuple = (0.0, 0.0), parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._spins: List[QDoubleSpinBox] = []
        for i, label in enumerate(["X", "Y"]):
            lbl = QLabel(label)
            lbl.setFixedWidth(12)
            layout.addWidget(lbl)

            spin = QDoubleSpinBox()
            spin.setRange(-9999.0, 9999.0)
            spin.setDecimals(3)
            spin.setSingleStep(0.1)
            spin.setValue(value[i] if i < len(value) else 0.0)
            spin.valueChanged.connect(self._on_value_changed)
            spin.editingFinished.connect(self._on_editing_finished)
            layout.addWidget(spin)
            self._spins.append(spin)

    def set_value(self, value: tuple) -> None:
        for i, spin in enumerate(self._spins):
            spin.blockSignals(True)
            spin.setValue(value[i] if i < len(value) else 0.0)
            spin.blockSignals(False)

    def get_value(self) -> tuple:
        return tuple(spin.value() for spin in self._spins)

    def _on_value_changed(self) -> None:
        self.value_changed.emit(self.get_value())

    def _on_editing_finished(self) -> None:
        self.editing_finished.emit()


class Vec3Editor(QWidget):
    """Редактор для vec3."""

    value_changed = pyqtSignal(tuple)
    editing_finished = pyqtSignal()

    def __init__(self, value: tuple = (0.0, 0.0, 0.0), parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._spins: List[QDoubleSpinBox] = []
        for i, label in enumerate(["X", "Y", "Z"]):
            lbl = QLabel(label)
            lbl.setFixedWidth(12)
            layout.addWidget(lbl)

            spin = QDoubleSpinBox()
            spin.setRange(-9999.0, 9999.0)
            spin.setDecimals(3)
            spin.setSingleStep(0.1)
            spin.setValue(value[i] if i < len(value) else 0.0)
            spin.valueChanged.connect(self._on_value_changed)
            spin.editingFinished.connect(self._on_editing_finished)
            layout.addWidget(spin)
            self._spins.append(spin)

    def set_value(self, value: tuple) -> None:
        for i, spin in enumerate(self._spins):
            spin.blockSignals(True)
            spin.setValue(value[i] if i < len(value) else 0.0)
            spin.blockSignals(False)

    def get_value(self) -> tuple:
        return tuple(spin.value() for spin in self._spins)

    def _on_value_changed(self) -> None:
        self.value_changed.emit(self.get_value())

    def _on_editing_finished(self) -> None:
        self.editing_finished.emit()


class Vec4Editor(QWidget):
    """Редактор для vec4."""

    value_changed = pyqtSignal(tuple)
    editing_finished = pyqtSignal()

    def __init__(self, value: tuple = (0.0, 0.0, 0.0, 0.0), parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._spins: List[QDoubleSpinBox] = []
        for i, label in enumerate(["X", "Y", "Z", "W"]):
            lbl = QLabel(label)
            lbl.setFixedWidth(12)
            layout.addWidget(lbl)

            spin = QDoubleSpinBox()
            spin.setRange(-9999.0, 9999.0)
            spin.setDecimals(3)
            spin.setSingleStep(0.1)
            spin.setValue(value[i] if i < len(value) else 0.0)
            spin.valueChanged.connect(self._on_value_changed)
            spin.editingFinished.connect(self._on_editing_finished)
            layout.addWidget(spin)
            self._spins.append(spin)

    def set_value(self, value: tuple) -> None:
        for i, spin in enumerate(self._spins):
            spin.blockSignals(True)
            spin.setValue(value[i] if i < len(value) else 0.0)
            spin.blockSignals(False)

    def get_value(self) -> tuple:
        return tuple(spin.value() for spin in self._spins)

    def _on_value_changed(self) -> None:
        self.value_changed.emit(self.get_value())

    def _on_editing_finished(self) -> None:
        self.editing_finished.emit()


class TextureSelector(QWidget):
    """
    Виджет выбора текстуры с превью.

    Показывает:
    - Миниатюру текстуры (или placeholder)
    - Комбобокс со списком текстур из ResourceManager
    """

    texture_changed = pyqtSignal(str)  # Имя текстуры или пустая строка для None
    editing_finished = pyqtSignal()

    PREVIEW_SIZE = 48

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._current_texture_name: str = ""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Превью текстуры
        self._preview = QLabel()
        self._preview.setFixedSize(self.PREVIEW_SIZE, self.PREVIEW_SIZE)
        self._preview.setStyleSheet(
            "background-color: #333; border: 1px solid #555; border-radius: 2px;"
        )
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setScaledContents(True)
        layout.addWidget(self._preview)

        # Комбобокс для выбора текстуры
        self._combo = QComboBox()
        self._combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._combo.currentTextChanged.connect(self._on_combo_changed)
        layout.addWidget(self._combo, 1)

        self._update_placeholder()

    def refresh_texture_list(self) -> None:
        """Обновить список текстур из ResourceManager."""
        from termin.visualization.core.resources import ResourceManager

        rm = ResourceManager.instance()
        names = rm.list_texture_names()

        self._combo.blockSignals(True)
        current = self._combo.currentText()
        self._combo.clear()
        self._combo.addItem("(None)")
        for name in names:
            # Пропускаем служебную белую текстуру
            if name == "__white_1x1__":
                continue
            self._combo.addItem(name)

        # Восстанавливаем выбор
        if current:
            idx = self._combo.findText(current)
            if idx >= 0:
                self._combo.setCurrentIndex(idx)
            else:
                self._combo.setCurrentIndex(0)
        self._combo.blockSignals(False)

    def set_texture_name(self, name: str | None) -> None:
        """Установить текущую текстуру по имени."""
        self._current_texture_name = name or ""

        self._combo.blockSignals(True)
        if not name:
            self._combo.setCurrentIndex(0)  # (None)
        else:
            idx = self._combo.findText(name)
            if idx >= 0:
                self._combo.setCurrentIndex(idx)
            else:
                # Текстура не найдена в списке — добавим её
                self._combo.addItem(name)
                self._combo.setCurrentText(name)
        self._combo.blockSignals(False)

        self._update_preview()

    def get_texture_name(self) -> str:
        """Получить имя текущей текстуры или пустую строку."""
        return self._current_texture_name

    def _on_combo_changed(self, text: str) -> None:
        """Обработчик изменения выбора в комбобоксе."""
        if text == "(None)":
            self._current_texture_name = ""
        else:
            self._current_texture_name = text

        self._update_preview()
        self.texture_changed.emit(self._current_texture_name)
        self.editing_finished.emit()

    def _update_preview(self) -> None:
        """Обновить превью текстуры."""
        if not self._current_texture_name:
            self._update_placeholder()
            return

        from termin.visualization.core.resources import ResourceManager

        rm = ResourceManager.instance()
        texture = rm.get_texture(self._current_texture_name)

        if texture is None:
            self._update_placeholder()
            return

        # Используем кэшированное превью из текстуры
        pixmap = texture.get_preview_pixmap(self.PREVIEW_SIZE)
        if pixmap is None:
            self._update_placeholder()
            return

        self._preview.setPixmap(pixmap)

    def _update_placeholder(self) -> None:
        """Показать placeholder вместо текстуры."""
        self._preview.clear()
        self._preview.setText("No\nTex")
        self._preview.setStyleSheet(
            "background-color: #333; border: 1px solid #555; "
            "border-radius: 2px; color: #666; font-size: 10px;"
        )


class MaterialInspector(QWidget):
    """
    Инспектор материала.

    Отображает:
    - Имя материала
    - Путь к шейдеру
    - Все uniform-свойства с редакторами по типу
    """

    material_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._material: Material | None = None
        self._shader_program: ShaderMultyPhaseProgramm | None = None
        self._uniform_widgets: Dict[str, QWidget] = {}
        self._phase_combos: List[tuple[int, QComboBox]] = []

        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(8)

        # Заголовок
        title = QLabel("Material Inspector")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        main_layout.addWidget(title)

        # Имя материала
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Material name")
        self._name_edit.editingFinished.connect(self._on_name_changed)
        name_layout.addWidget(self._name_edit)
        main_layout.addLayout(name_layout)

        # UUID (read-only)
        uuid_layout = QHBoxLayout()
        uuid_layout.addWidget(QLabel("UUID:"))
        self._uuid_label = QLabel()
        self._uuid_label.setStyleSheet("color: #888; font-family: monospace; font-size: 10px;")
        self._uuid_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        uuid_layout.addWidget(self._uuid_label, 1)
        main_layout.addLayout(uuid_layout)

        # Выбор шейдера
        shader_layout = QHBoxLayout()
        shader_layout.addWidget(QLabel("Shader:"))
        self._shader_combo = QComboBox()
        self._shader_combo.currentTextChanged.connect(self._on_shader_changed)
        shader_layout.addWidget(self._shader_combo, 1)
        main_layout.addLayout(shader_layout)

        # Разделитель
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line)

        # Скролл-область для свойств
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._properties_widget = QWidget()
        self._properties_layout = QVBoxLayout(self._properties_widget)
        self._properties_layout.setContentsMargins(0, 0, 0, 0)
        self._properties_layout.setSpacing(4)
        self._properties_layout.addStretch()

        scroll.setWidget(self._properties_widget)
        main_layout.addWidget(scroll, 1)

    def set_material(self, material: Material | None) -> None:
        """Установить материал для редактирования."""
        self._material = material
        self._rebuild_ui()

    def load_material_file(self, path: str | Path) -> None:
        """Загрузить материал из .material файла."""
        from termin.visualization.core.resources import ResourceManager

        path = Path(path)
        if not path.exists():
            return

        rm = ResourceManager.instance()

        # Получаем имя материала из имени файла
        material_name = path.stem

        # Получаем материал из ResourceManager (он уже загружен при сканировании)
        self._material = rm.get_material(material_name)

        if self._material is None:
            return

        # Загружаем shader_program из ResourceManager
        shader_name = self._material.shader_name
        self._shader_program = rm.get_shader(shader_name)

        self._rebuild_ui()
        self.material_changed.emit()

    def save_material_file(self, path: str | Path | None = None) -> bool:
        """
        Сохранить материал в .material файл.

        Args:
            path: Путь для сохранения. Если None, используется source_path материала
                  или открывается диалог выбора файла.

        Returns:
            True если сохранение успешно
        """
        from termin._native import log

        if self._material is None:
            log.warning("[MaterialInspector] save_material_file: material is None")
            return False

        from termin.visualization.core.resources import ResourceManager
        rm = ResourceManager.instance()
        asset = rm.get_material_asset(self._material.name)

        log.info(f"[MaterialInspector] save_material_file: material.name={self._material.name}, asset={asset}")

        # Определяем путь для сохранения
        if path is None:
            path = asset.source_path if asset else self._material.source_path
            log.info(f"[MaterialInspector] save_material_file: resolved path={path}")

        if path is None:
            # Открываем диалог выбора файла
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Material",
                f"{self._material.name or 'material'}.material",
                "Material Files (*.material);;All Files (*)",
                options=QFileDialog.Option.DontUseNativeDialog,
            )
            if not path:
                return False

        path = Path(path)

        # Добавляем расширение если не указано
        if path.suffix != ".material":
            path = path.with_suffix(".material")

        if asset is not None:
            # Use asset's save method (handles UUID automatically)
            log.info(f"[MaterialInspector] saving via asset.save_to_file({path})")
            if asset.save_to_file(path):
                self._material.source_path = str(path)
                log.info("[MaterialInspector] save SUCCESS")
                return True
            else:
                log.error(f"[MaterialInspector] asset.save_to_file returned False")
                QMessageBox.critical(
                    self,
                    "Error Saving Material",
                    f"Failed to save material:\n{path}",
                )
                return False
        else:
            # No asset - save directly (shouldn't normally happen)
            log.warning("[MaterialInspector] No asset found, saving directly")
            try:
                from termin.assets.material_asset import _save_material_file
                _save_material_file(self._material, path, uuid="")
                self._material.source_path = str(path)
                return True
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error Saving Material",
                    f"Failed to save material:\n{path}\n\nError: {e}",
                )
                return False

    def _rebuild_ui(self) -> None:
        """Перестроить UI под текущий материал."""
        from termin.visualization.core.resources import ResourceManager

        # Очищаем старые виджеты свойств
        self._uniform_widgets.clear()
        self._phase_combos = []
        while self._properties_layout.count() > 1:
            item = self._properties_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Обновляем список шейдеров в комбобоксе
        rm = ResourceManager.instance()
        self._shader_combo.blockSignals(True)
        self._shader_combo.clear()
        shader_names = rm.list_shader_names()
        self._shader_combo.addItems(shader_names)

        if self._material is None:
            self._name_edit.setText("")
            self._uuid_label.setText("")
            self._shader_combo.setCurrentIndex(-1)
            self._shader_combo.blockSignals(False)
            return

        # Имя материала
        self._name_edit.setText(self._material.name or "")

        # UUID (from MaterialAsset)
        asset = rm.get_material_asset(self._material.name)
        self._uuid_label.setText(asset.uuid if asset else "—")

        # Выбор шейдера
        shader_name = self._material.shader_name
        idx = self._shader_combo.findText(shader_name)
        if idx >= 0:
            self._shader_combo.setCurrentIndex(idx)
        self._shader_combo.blockSignals(False)

        # Phase selectors for phases with multiple available marks
        self._phase_combos: List[tuple[int, QComboBox]] = []
        for i, phase in enumerate(self._material.phases):
            available = phase.available_marks
            if len(available) > 1:
                self._create_phase_selector(i, phase, available)
            elif len(available) == 1:
                self._create_phase_label(available[0])

        # Собираем все properties из всех фаз
        all_properties: Dict[str, MaterialProperty] = {}
        if self._shader_program is not None:
            for phase in self._shader_program.phases:
                for prop in phase.uniforms:
                    if prop.name not in all_properties:
                        all_properties[prop.name] = prop

        # Создаём редакторы для каждого property
        for prop in all_properties.values():
            self._create_property_editor(prop)

    def _create_phase_label(self, phase_mark: str) -> None:
        """Create a simple label showing the phase when there's no choice."""
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 2, 0, 2)
        row_layout.setSpacing(8)

        label = QLabel("Render Mode:")
        label.setFixedWidth(100)
        row_layout.addWidget(label)

        value_label = QLabel(phase_mark)
        value_label.setStyleSheet("color: #888;")
        row_layout.addWidget(value_label, 1)

        self._properties_layout.insertWidget(
            self._properties_layout.count() - 1, row_widget
        )

    def _create_phase_selector(self, phase_index: int, phase: Any, available_marks: List[str]) -> None:
        """Create phase selector ComboBox for a phase with multiple available marks."""
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 2, 0, 2)
        row_layout.setSpacing(8)

        # Label shows phase index if multiple phases
        label_text = f"Phase {phase_index + 1}:" if len(self._material.phases) > 1 else "Render Mode:"
        label = QLabel(label_text)
        label.setFixedWidth(100)
        row_layout.addWidget(label)

        combo = QComboBox()
        for mark in available_marks:
            combo.addItem(mark, mark)

        # Set current value
        current = phase.phase_mark
        index = combo.findData(current)
        if index >= 0:
            combo.setCurrentIndex(index)

        combo.currentIndexChanged.connect(
            lambda idx, pi=phase_index: self._on_phase_mark_changed(pi, idx)
        )
        row_layout.addWidget(combo, 1)

        self._phase_combos.append((phase_index, combo))
        self._properties_layout.insertWidget(
            self._properties_layout.count() - 1, row_widget
        )

    def _on_phase_mark_changed(self, phase_index: int, combo_index: int) -> None:
        """Handle phase mark selection change."""
        if self._material is None or phase_index >= len(self._material.phases):
            return

        combo = None
        for pi, c in self._phase_combos:
            if pi == phase_index:
                combo = c
                break

        if combo is None:
            return

        new_mark = combo.itemData(combo_index)
        self._material.phases[phase_index].set_phase_mark(new_mark)
        self.material_changed.emit()
        self.save_material_file()

    def _create_property_editor(self, prop: MaterialProperty) -> None:
        """Создать редактор для свойства материала."""
        # Получаем текущее значение из материала
        current_value = None
        if self._material is not None:
            current_value = self._material.uniforms.get(prop.name)
        if current_value is None:
            current_value = prop.default

        # Лейбл
        label_text = prop.label or prop.name

        # Создаём редактор в зависимости от типа
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 2, 0, 2)
        row_layout.setSpacing(8)

        label = QLabel(label_text + ":")
        label.setFixedWidth(100)
        row_layout.addWidget(label)

        editor: QWidget | None = None

        if prop.property_type == "Float":
            editor = self._create_float_editor(prop, current_value)
        elif prop.property_type == "Int":
            editor = self._create_int_editor(prop, current_value)
        elif prop.property_type == "Bool":
            editor = self._create_bool_editor(prop, current_value)
        elif prop.property_type == "Vec2":
            editor = self._create_vec2_editor(prop, current_value)
        elif prop.property_type == "Vec3":
            editor = self._create_vec3_editor(prop, current_value)
        elif prop.property_type == "Vec4":
            editor = self._create_vec4_editor(prop, current_value)
        elif prop.property_type == "Color":
            editor = self._create_color_editor(prop, current_value)
        elif prop.property_type == "Texture":
            editor = self._create_texture_editor(prop, current_value)

        if editor is not None:
            row_layout.addWidget(editor, 1)
            self._uniform_widgets[prop.name] = editor

        # Вставляем перед stretch
        self._properties_layout.insertWidget(
            self._properties_layout.count() - 1,
            row_widget
        )

    def _create_float_editor(self, prop: MaterialProperty, value: Any) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setDecimals(3)
        spin.setSingleStep(0.1)

        if prop.range_min is not None and prop.range_max is not None:
            spin.setRange(prop.range_min, prop.range_max)
        else:
            spin.setRange(-9999.0, 9999.0)

        spin.setValue(float(value) if value is not None else 0.0)
        spin.valueChanged.connect(
            lambda v, name=prop.name: self._on_uniform_changed(name, v)
        )
        spin.editingFinished.connect(self._on_editing_finished)
        return spin

    def _create_int_editor(self, prop: MaterialProperty, value: Any) -> QSpinBox:
        spin = QSpinBox()

        if prop.range_min is not None and prop.range_max is not None:
            spin.setRange(int(prop.range_min), int(prop.range_max))
        else:
            spin.setRange(-9999, 9999)

        spin.setValue(int(value) if value is not None else 0)
        spin.valueChanged.connect(
            lambda v, name=prop.name: self._on_uniform_changed(name, v)
        )
        spin.editingFinished.connect(self._on_editing_finished)
        return spin

    def _create_bool_editor(self, prop: MaterialProperty, value: Any) -> QCheckBox:
        checkbox = QCheckBox()
        checkbox.setChecked(bool(value) if value is not None else False)
        checkbox.stateChanged.connect(
            lambda state, name=prop.name: self._on_uniform_changed(name, state == Qt.CheckState.Checked.value)
        )
        checkbox.stateChanged.connect(lambda _: self._on_editing_finished())
        return checkbox

    def _create_vec2_editor(self, prop: MaterialProperty, value: Any) -> Vec2Editor:
        val = value if value is not None else (0.0, 0.0)
        if isinstance(val, np.ndarray):
            val = tuple(val.tolist())
        editor = Vec2Editor(val)
        editor.value_changed.connect(
            lambda v, name=prop.name: self._on_uniform_changed(name, np.array(v, dtype=np.float32))
        )
        editor.editing_finished.connect(self._on_editing_finished)
        return editor

    def _create_vec3_editor(self, prop: MaterialProperty, value: Any) -> Vec3Editor:
        val = value if value is not None else (0.0, 0.0, 0.0)
        if isinstance(val, np.ndarray):
            val = tuple(val.tolist())
        editor = Vec3Editor(val)
        editor.value_changed.connect(
            lambda v, name=prop.name: self._on_uniform_changed(name, np.array(v, dtype=np.float32))
        )
        editor.editing_finished.connect(self._on_editing_finished)
        return editor

    def _create_vec4_editor(self, prop: MaterialProperty, value: Any) -> Vec4Editor:
        val = value if value is not None else (0.0, 0.0, 0.0, 0.0)
        if isinstance(val, np.ndarray):
            val = tuple(val.tolist())
        editor = Vec4Editor(val)
        editor.value_changed.connect(
            lambda v, name=prop.name: self._on_uniform_changed(name, np.array(v, dtype=np.float32))
        )
        editor.editing_finished.connect(self._on_editing_finished)
        return editor

    def _create_color_editor(self, prop: MaterialProperty, value: Any) -> ColorButton:
        val = value if value is not None else (1.0, 1.0, 1.0, 1.0)
        if isinstance(val, np.ndarray):
            val = tuple(val.tolist())
        editor = ColorButton(val)
        editor.color_changed.connect(
            lambda v, name=prop.name: self._on_uniform_changed(name, v)  # v is Vec4
        )
        editor.editing_finished.connect(self._on_editing_finished)
        return editor

    def _create_texture_editor(self, prop: MaterialProperty, value: Any) -> TextureSelector:
        from termin.visualization.core.resources import ResourceManager
        from termin.visualization.render.texture import Texture

        editor = TextureSelector()
        editor.refresh_texture_list()

        # Определяем текущее имя текстуры
        texture_name = ""
        if self._material is not None:
            texture = self._material.textures.get(prop.name)
            if texture is not None:
                rm = ResourceManager.instance()
                texture_name = rm.find_texture_name(texture) or ""
                # Пропускаем белую текстуру - показываем как None
                if texture_name == "__white_1x1__":
                    texture_name = ""

        editor.set_texture_name(texture_name)
        editor.texture_changed.connect(
            lambda name, uniform_name=prop.name: self._on_texture_changed(uniform_name, name)
        )
        editor.editing_finished.connect(self._on_editing_finished)

        return editor

    def _on_uniform_changed(self, name: str, value: Any) -> None:
        """Обработчик изменения uniform-значения."""
        if self._material is None:
            return

        # Convert numpy arrays to Vec3/Vec4 for C++ set_param
        from termin.geombase import Vec3
        converted_value = value
        if isinstance(value, np.ndarray):
            if value.size == 3:
                converted_value = Vec3(float(value[0]), float(value[1]), float(value[2]))
            elif value.size == 4:
                converted_value = Vec4(float(value[0]), float(value[1]), float(value[2]), float(value[3]))

        # Обновляем значение во всех фазах материала
        for phase in self._material.phases:
            phase.set_param(name, converted_value)

        self.material_changed.emit()

    def _on_name_changed(self) -> None:
        """Обработчик изменения имени материала."""
        if self._material is None:
            return
        self._material.name = self._name_edit.text()
        self.material_changed.emit()
        self.save_material_file()

    def _on_shader_changed(self, shader_name: str) -> None:
        """Обработчик изменения шейдера в комбобоксе."""
        if not shader_name or self._material is None:
            return

        from termin.visualization.core.resources import ResourceManager
        from termin._native import log

        rm = ResourceManager.instance()
        program = rm.get_shader(shader_name)

        if program is None:
            return

        # Get shader asset UUID for hot-reload support
        shader_asset = rm._shader_assets.get(shader_name)
        shader_uuid = shader_asset.uuid if shader_asset else ""

        log.info(f"[MaterialInspector] _on_shader_changed shader={shader_name} shader_uuid={shader_uuid}")

        # Обновляем shader_program и пересоздаём phases материала
        from termin.assets.shader_asset import update_material_shader
        self._shader_program = program
        update_material_shader(self._material, program, shader_name, shader_uuid)

        # Перестраиваем UI (редакторы свойств)
        self._rebuild_ui()
        self.material_changed.emit()
        self.save_material_file()

    def _on_texture_changed(self, uniform_name: str, texture_name: str) -> None:
        """Обработчик изменения текстуры."""
        if self._material is None:
            return

        from termin.visualization.core.resources import ResourceManager
        from termin.visualization.core.texture_handle import get_white_texture_handle

        rm = ResourceManager.instance()

        if texture_name:
            # Получаем текстуру по имени
            texture_handle = rm.get_texture_handle(texture_name)
        else:
            # None - используем белую текстуру
            texture_handle = get_white_texture_handle()

        if texture_handle is not None:
            # Обновляем текстуру во всех фазах материала
            for phase in self._material.phases:
                phase.textures[uniform_name] = texture_handle

        self.material_changed.emit()
        self.save_material_file()

    def _on_editing_finished(self) -> None:
        """Обработчик окончания редактирования — автосохранение."""
        self.save_material_file()

    @property
    def material(self) -> Material | None:
        """Текущий материал."""
        return self._material
