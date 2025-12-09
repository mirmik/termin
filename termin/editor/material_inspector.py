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
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from termin.editor.color_dialog import ColorDialog
from termin.visualization.core.material import Material
from termin.visualization.render.shader_parser import (
    ShaderMultyPhaseProgramm,
    MaterialProperty,
)


class ColorButton(QPushButton):
    """Кнопка для выбора цвета с превью."""

    color_changed = pyqtSignal(tuple)

    def __init__(self, color: tuple = (1.0, 1.0, 1.0, 1.0), parent: QWidget | None = None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(60, 24)
        self._update_style()
        self.clicked.connect(self._on_clicked)

    def set_color(self, color: tuple) -> None:
        self._color = color
        self._update_style()

    def get_color(self) -> tuple:
        return self._color

    def _update_style(self) -> None:
        r, g, b, a = self._color
        # Конвертируем в 0-255
        r255 = int(r * 255)
        g255 = int(g * 255)
        b255 = int(b * 255)
        self.setStyleSheet(
            f"background-color: rgba({r255}, {g255}, {b255}, {int(a * 255)}); "
            f"border: 1px solid #555;"
        )

    def _on_clicked(self) -> None:
        dlg = ColorDialog(self._color, self)
        dlg.color_changed.connect(self._on_dialog_color_changed)
        if dlg.exec() == ColorDialog.DialogCode.Accepted:
            self._color = dlg.get_color_01()
            self._update_style()
            self.color_changed.emit(self._color)

    def _on_dialog_color_changed(self) -> None:
        """Обработчик изменения цвета в диалоге (live preview)."""
        dlg = self.sender()
        if dlg is not None:
            self._color = dlg.get_color_01()
            self._update_style()
            self.color_changed.emit(self._color)


class Vec2Editor(QWidget):
    """Редактор для vec2."""

    value_changed = pyqtSignal(tuple)

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


class Vec3Editor(QWidget):
    """Редактор для vec3."""

    value_changed = pyqtSignal(tuple)

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


class Vec4Editor(QWidget):
    """Редактор для vec4."""

    value_changed = pyqtSignal(tuple)

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

        # Кнопка Save
        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(self._on_save_clicked)
        main_layout.addWidget(self._save_btn)

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

        try:
            self._material = Material.load_from_material_file(str(path))

            # Загружаем shader_program из ResourceManager
            shader_name = self._material.shader_name
            rm = ResourceManager.instance()
            self._shader_program = rm.get_shader(shader_name)

            self._rebuild_ui()
            self.material_changed.emit()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Loading Material",
                f"Failed to load material:\n{path}\n\nError: {e}",
            )

    def save_material_file(self, path: str | Path | None = None) -> bool:
        """
        Сохранить материал в .material файл.

        Args:
            path: Путь для сохранения. Если None, используется source_path материала
                  или открывается диалог выбора файла.

        Returns:
            True если сохранение успешно
        """
        if self._material is None:
            return False

        # Определяем путь для сохранения
        if path is None:
            path = self._material.source_path

        if path is None:
            # Открываем диалог выбора файла
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Material",
                f"{self._material.name or 'material'}.material",
                "Material Files (*.material);;All Files (*)",
            )
            if not path:
                return False

        path = Path(path)

        # Добавляем расширение если не указано
        if path.suffix != ".material":
            path = path.with_suffix(".material")

        try:
            # Формируем данные материала
            data = self._material.serialize_to_material_file()

            # Сохраняем
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Обновляем source_path
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
            self._shader_combo.setCurrentIndex(-1)
            self._shader_combo.blockSignals(False)
            return

        # Имя материала
        self._name_edit.setText(self._material.name or "")

        # Выбор шейдера
        shader_name = self._material.shader_name
        idx = self._shader_combo.findText(shader_name)
        if idx >= 0:
            self._shader_combo.setCurrentIndex(idx)
        self._shader_combo.blockSignals(False)

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
        return spin

    def _create_bool_editor(self, prop: MaterialProperty, value: Any) -> QCheckBox:
        checkbox = QCheckBox()
        checkbox.setChecked(bool(value) if value is not None else False)
        checkbox.stateChanged.connect(
            lambda state, name=prop.name: self._on_uniform_changed(name, state == Qt.CheckState.Checked.value)
        )
        return checkbox

    def _create_vec2_editor(self, prop: MaterialProperty, value: Any) -> Vec2Editor:
        val = value if value is not None else (0.0, 0.0)
        if isinstance(val, np.ndarray):
            val = tuple(val.tolist())
        editor = Vec2Editor(val)
        editor.value_changed.connect(
            lambda v, name=prop.name: self._on_uniform_changed(name, np.array(v, dtype=np.float32))
        )
        return editor

    def _create_vec3_editor(self, prop: MaterialProperty, value: Any) -> Vec3Editor:
        val = value if value is not None else (0.0, 0.0, 0.0)
        if isinstance(val, np.ndarray):
            val = tuple(val.tolist())
        editor = Vec3Editor(val)
        editor.value_changed.connect(
            lambda v, name=prop.name: self._on_uniform_changed(name, np.array(v, dtype=np.float32))
        )
        return editor

    def _create_vec4_editor(self, prop: MaterialProperty, value: Any) -> Vec4Editor:
        val = value if value is not None else (0.0, 0.0, 0.0, 0.0)
        if isinstance(val, np.ndarray):
            val = tuple(val.tolist())
        editor = Vec4Editor(val)
        editor.value_changed.connect(
            lambda v, name=prop.name: self._on_uniform_changed(name, np.array(v, dtype=np.float32))
        )
        return editor

    def _create_color_editor(self, prop: MaterialProperty, value: Any) -> ColorButton:
        val = value if value is not None else (1.0, 1.0, 1.0, 1.0)
        if isinstance(val, np.ndarray):
            val = tuple(val.tolist())
        editor = ColorButton(val)
        editor.color_changed.connect(
            lambda v, name=prop.name: self._on_uniform_changed(name, np.array(v, dtype=np.float32))
        )
        return editor

    def _create_texture_editor(self, prop: MaterialProperty, value: Any) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        path_label = QLabel(str(value) if value else "None")
        path_label.setStyleSheet("color: #888;")
        layout.addWidget(path_label, 1)

        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(30)
        browse_btn.clicked.connect(
            lambda _, name=prop.name, lbl=path_label: self._on_browse_texture(name, lbl)
        )
        layout.addWidget(browse_btn)

        return widget

    def _on_uniform_changed(self, name: str, value: Any) -> None:
        """Обработчик изменения uniform-значения."""
        if self._material is None:
            return

        # Обновляем значение во всех фазах материала
        for phase in self._material.phases:
            phase.uniforms[name] = value

        self.material_changed.emit()

    def _on_name_changed(self) -> None:
        """Обработчик изменения имени материала."""
        if self._material is None:
            return
        self._material.name = self._name_edit.text()
        self.material_changed.emit()

    def _on_shader_changed(self, shader_name: str) -> None:
        """Обработчик изменения шейдера в комбобоксе."""
        if not shader_name or self._material is None:
            return

        from termin.visualization.core.resources import ResourceManager

        rm = ResourceManager.instance()
        program = rm.get_shader(shader_name)

        if program is None:
            return

        # Обновляем shader_program и shader_name
        self._shader_program = program
        self._material.shader_name = shader_name

        # Перестраиваем UI (редакторы свойств)
        self._rebuild_ui()
        self.material_changed.emit()

    def _on_browse_texture(self, uniform_name: str, label: QLabel) -> None:
        """Обработчик выбора текстуры."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Texture",
            "",
            "Image Files (*.png *.jpg *.jpeg *.tga *.bmp);;All Files (*)",
        )
        if path:
            label.setText(Path(path).name)
            # TODO: Загрузить текстуру и установить в материал
            self.material_changed.emit()

    def _on_save_clicked(self) -> None:
        """Обработчик нажатия кнопки Save."""
        if self._material is None:
            return
        self.save_material_file()

    @property
    def material(self) -> Material | None:
        """Текущий материал."""
        return self._material
