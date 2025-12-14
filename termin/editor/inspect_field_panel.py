"""
Generic panel for editing objects with inspect_fields.

This panel can be used for any object that has an `inspect_fields` class attribute,
including Components and RenderPasses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Optional

import numpy as np

from PyQt6.QtWidgets import (
    QWidget,
    QFormLayout,
    QLabel,
    QDoubleSpinBox,
    QCheckBox,
    QLineEdit,
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QSlider,
    QSpinBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from termin.editor.inspect_field import InspectField


def _collect_inspect_fields(cls: type) -> dict[str, InspectField]:
    """Collect inspect_fields from class hierarchy (base classes first)."""
    result = {}
    for klass in reversed(cls.__mro__):
        fields = getattr(klass, "inspect_fields", None)
        if fields:
            result.update(fields)
    return result

if TYPE_CHECKING:
    from termin.visualization.core.resources import ResourceManager


def _values_equal(a, b) -> bool:
    """
    Safe comparison that handles numpy arrays and sequences.

    Returns True if values are equal, False otherwise.
    """
    try:
        # Handle numpy arrays
        if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
            a_arr = np.asarray(a)
            b_arr = np.asarray(b)
            if a_arr.shape != b_arr.shape:
                return False
            return bool(np.allclose(a_arr, b_arr))

        # Handle tuples/lists - compare element by element
        if isinstance(a, (tuple, list)) and isinstance(b, (tuple, list)):
            if len(a) != len(b):
                return False
            return all(_values_equal(x, y) for x, y in zip(a, b))

        # Standard comparison
        return a == b
    except Exception:
        return False


def _to_qcolor(value) -> QColor:
    """
    Converts color value to QColor.
    Supports:
    - QColor
    - tuple/list (r, g, b) or (r, g, b, a) in range 0..1
    - numpy array
    """
    if isinstance(value, QColor):
        return value
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        r = float(value[0])
        g = float(value[1])
        b = float(value[2])
        a = float(value[3]) if len(value) > 3 else 1.0
        return QColor.fromRgbF(
            max(0.0, min(1.0, r)),
            max(0.0, min(1.0, g)),
            max(0.0, min(1.0, b)),
            max(0.0, min(1.0, a)),
        )
    try:
        arr = np.asarray(value).reshape(-1)
        if arr.size >= 3:
            r = float(arr[0])
            g = float(arr[1])
            b = float(arr[2])
            a = float(arr[3]) if arr.size > 3 else 1.0
            return QColor.fromRgbF(
                max(0.0, min(1.0, r)),
                max(0.0, min(1.0, g)),
                max(0.0, min(1.0, b)),
                max(0.0, min(1.0, a)),
            )
    except Exception:
        pass
    return QColor(255, 255, 255)


class InspectFieldPanel(QWidget):
    """
    Generic panel for editing objects with inspect_fields.

    Usage:
        panel = InspectFieldPanel()
        panel.set_target(my_object)
        panel.field_changed.connect(on_change)
    """

    field_changed = pyqtSignal(str, object, object)  # field_key, old_value, new_value

    def __init__(
        self,
        resources: Optional["ResourceManager"] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._target: Any = None
        self._fields: dict[str, InspectField] = {}
        self._widgets: dict[str, QWidget] = {}
        self._updating_from_model = False
        self._resources = resources

        layout = QFormLayout(self)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setContentsMargins(0, 0, 0, 0)
        self._layout = layout

    def set_resources(self, resources: "ResourceManager") -> None:
        """Set resource manager for material/mesh lookups."""
        self._resources = resources

    def set_target(self, target: Any) -> None:
        """Set the object to inspect."""
        # Clear existing widgets
        for i in reversed(range(self._layout.count())):
            item = self._layout.itemAt(i)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        self._widgets.clear()
        self._target = target

        if target is None:
            return

        fields = _collect_inspect_fields(target.__class__)
        if not fields:
            return

        self._fields = fields

        self._updating_from_model = True
        try:
            for key, field in fields.items():
                label = field.label or key
                widget = self._create_widget_for_field(field)
                self._widgets[key] = widget

                # Buttons span the full row, no separate label
                if field.kind == "button":
                    self._layout.addRow(widget)
                else:
                    self._layout.addRow(QLabel(label), widget)

                    value = field.get_value(target)
                    self._set_widget_value(widget, value, field)

                self._connect_widget(widget, key, field)
        finally:
            self._updating_from_model = False

    def refresh(self) -> None:
        """Refresh widget values from the target object."""
        if self._target is None:
            return

        self._updating_from_model = True
        try:
            for key, field in self._fields.items():
                widget = self._widgets.get(key)
                if widget is None:
                    continue
                value = field.get_value(self._target)
                self._set_widget_value(widget, value, field)
        finally:
            self._updating_from_model = False

    @property
    def target(self) -> Any:
        """Current target object."""
        return self._target

    def _create_widget_for_field(self, field: InspectField) -> QWidget:
        kind = field.kind

        if kind in ("float", "int"):
            sb = QDoubleSpinBox()
            sb.setDecimals(4 if kind == "float" else 0)
            sb.setRange(
                field.min if field.min is not None else -1e9,
                field.max if field.max is not None else 1e9,
            )
            if field.step is not None:
                sb.setSingleStep(field.step)
            return sb

        if kind == "bool":
            return QCheckBox()

        if kind == "string":
            le = QLineEdit()
            # Read-only если есть getter, но нет setter и нет path
            if field.getter is not None and field.setter is None and field.path is None:
                le.setReadOnly(True)
            return le

        if kind == "vec3":
            row = QWidget()
            hl = QHBoxLayout(row)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(2)
            boxes = []
            for _ in range(3):
                sb = QDoubleSpinBox()
                sb.setDecimals(4)
                sb.setRange(
                    field.min if field.min is not None else -1e9,
                    field.max if field.max is not None else 1e9,
                )
                if field.step is not None:
                    sb.setSingleStep(field.step)
                hl.addWidget(sb)
                boxes.append(sb)
            row._boxes = boxes
            return row

        if kind == "slider":
            # Слайдер + спинбокс в одном ряду
            row = QWidget()
            hl = QHBoxLayout(row)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(4)

            min_val = int(field.min) if field.min is not None else 0
            max_val = int(field.max) if field.max is not None else 100

            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(min_val, max_val)
            slider.setTickPosition(QSlider.TickPosition.NoTicks)

            spinbox = QSpinBox()
            spinbox.setRange(min_val, max_val)
            spinbox.setFixedWidth(50)

            # Синхронизация слайдера и спинбокса
            slider.valueChanged.connect(spinbox.setValue)
            spinbox.valueChanged.connect(slider.setValue)

            hl.addWidget(slider, stretch=1)
            hl.addWidget(spinbox)

            row._slider = slider
            row._spinbox = spinbox
            return row

        if kind == "material" and self._resources is not None:
            combo = QComboBox()
            names = self._resources.list_material_names()
            for n in names:
                combo.addItem(n)
            return combo

        if kind == "mesh" and self._resources is not None:
            combo = QComboBox()
            names = self._resources.list_mesh_names()
            for n in names:
                combo.addItem(n)
            return combo

        if kind == "voxel_grid" and self._resources is not None:
            combo = QComboBox()
            names = self._resources.list_voxel_grid_names()
            for n in names:
                combo.addItem(n)
            return combo

        if kind == "navmesh" and self._resources is not None:
            combo = QComboBox()
            names = self._resources.list_navmesh_names()
            for n in names:
                combo.addItem(n)
            return combo

        if kind == "enum":
            combo = QComboBox()
            if field.choices:
                for value, label in field.choices:
                    combo.addItem(label, userData=value)
            return combo

        if kind == "color":
            btn = QPushButton()
            btn.setAutoFillBackground(True)
            btn._current_color = None

            def set_btn_color(color: QColor):
                btn._current_color = (
                    color.redF(),
                    color.greenF(),
                    color.blueF(),
                    color.alphaF(),
                )
                pal = btn.palette()
                pal.setColor(btn.backgroundRole(), color)
                btn.setPalette(pal)
                btn.setText(
                    f"{color.redF():.2f}, {color.greenF():.2f}, "
                    f"{color.blueF():.2f}, {color.alphaF():.2f}"
                )

            btn._set_color = set_btn_color
            return btn

        if kind == "button":
            btn = QPushButton(field.label or "Action")
            btn._action = field.action
            btn._field = field
            return btn

        # Fallback: read-only line edit
        le = QLineEdit()
        le.setReadOnly(True)
        return le

    def _set_widget_value(self, w: QWidget, value: Any, field: InspectField) -> None:
        if isinstance(w, QDoubleSpinBox):
            w.setValue(float(value) if value is not None else 0.0)
            return

        if isinstance(w, QCheckBox):
            w.setChecked(bool(value) if value is not None else False)
            return

        if isinstance(w, QLineEdit) and field.kind == "string":
            w.setText(str(value) if value is not None else "")
            return

        if hasattr(w, "_boxes"):
            if value is not None:
                arr = np.asarray(value).reshape(-1)
                for sb, v in zip(w._boxes, arr):
                    sb.setValue(float(v))
            else:
                for sb in w._boxes:
                    sb.setValue(0.0)
            return

        if hasattr(w, "_slider") and field.kind == "slider":
            int_val = int(value) if value is not None else 0
            w._slider.setValue(int_val)
            return

        if isinstance(w, QComboBox) and field.kind == "material":
            if value is None or self._resources is None:
                w.setCurrentIndex(-1)
                return
            name = self._resources.find_material_name(value)
            if name is None:
                w.setCurrentIndex(-1)
                return
            idx = w.findText(name)
            w.setCurrentIndex(idx if idx >= 0 else -1)
            return

        if isinstance(w, QComboBox) and field.kind == "mesh":
            if self._resources is None:
                w.setCurrentIndex(-1)
                return

            # Refresh mesh list if changed
            existing = [w.itemText(i) for i in range(w.count())]
            all_names = self._resources.list_mesh_names()
            if existing != all_names:
                w.clear()
                for n in all_names:
                    w.addItem(n)

            if value is None:
                w.setCurrentIndex(-1)
                return
            name = self._resources.find_mesh_name(value)
            if name is None:
                w.setCurrentIndex(-1)
                return
            idx = w.findText(name)
            w.setCurrentIndex(idx if idx >= 0 else -1)
            return

        if isinstance(w, QComboBox) and field.kind == "voxel_grid":
            if self._resources is None:
                w.setCurrentIndex(-1)
                return

            # Refresh voxel grid list if changed
            existing = [w.itemText(i) for i in range(w.count())]
            all_names = self._resources.list_voxel_grid_names()
            if existing != all_names:
                w.clear()
                for n in all_names:
                    w.addItem(n)

            if value is None:
                w.setCurrentIndex(-1)
                return
            name = self._resources.find_voxel_grid_name(value)
            if name is None:
                w.setCurrentIndex(-1)
                return
            idx = w.findText(name)
            w.setCurrentIndex(idx if idx >= 0 else -1)
            return

        if isinstance(w, QComboBox) and field.kind == "navmesh":
            if self._resources is None:
                w.setCurrentIndex(-1)
                return

            # Refresh navmesh list if changed
            existing = [w.itemText(i) for i in range(w.count())]
            all_names = self._resources.list_navmesh_names()
            if existing != all_names:
                w.clear()
                for n in all_names:
                    w.addItem(n)

            # value — это имя navmesh (строка)
            name = value if isinstance(value, str) else None
            if name is None or name == "":
                w.setCurrentIndex(-1)
                return
            idx = w.findText(name)
            w.setCurrentIndex(idx if idx >= 0 else -1)
            return

        if isinstance(w, QComboBox) and field.kind == "enum":
            if field.choices:
                for i in range(w.count()):
                    item_data = w.itemData(i)
                    # Safe comparison for numpy arrays and other sequences
                    if _values_equal(item_data, value):
                        w.setCurrentIndex(i)
                        return
                w.setCurrentIndex(-1)
            else:
                idx = w.findText(str(value) if value is not None else "")
                w.setCurrentIndex(idx if idx >= 0 else -1)
            return

        if isinstance(w, QPushButton) and field.kind == "color":
            qcol = _to_qcolor(value) if value is not None else QColor(255, 255, 255)
            if hasattr(w, "_set_color"):
                w._set_color(qcol)
            return

        # Fallback for read-only
        if isinstance(w, QLineEdit):
            w.setText(str(value) if value is not None else "")

    def _connect_widget(self, w: QWidget, key: str, field: InspectField) -> None:
        def commit():
            if self._updating_from_model or self._target is None:
                return

            old_value = field.get_value(self._target)
            new_value = self._read_widget_value(w, field)

            # Set value directly
            field.set_value(self._target, new_value)

            # Emit signal for external handling
            self.field_changed.emit(key, old_value, new_value)

        if isinstance(w, QDoubleSpinBox):
            w.valueChanged.connect(lambda _v: commit())
        elif isinstance(w, QCheckBox):
            w.stateChanged.connect(lambda _s: commit())
        elif isinstance(w, QLineEdit) and field.kind == "string":
            # Не подключаем commit для read-only полей
            if not (field.getter is not None and field.setter is None and field.path is None):
                w.textEdited.connect(lambda _t: commit())
                w.editingFinished.connect(commit)
        elif hasattr(w, "_boxes"):
            for sb in w._boxes:
                sb.valueChanged.connect(lambda _v: commit())
        elif hasattr(w, "_slider") and field.kind == "slider":
            w._slider.valueChanged.connect(lambda _v: commit())
        elif isinstance(w, QComboBox):
            w.currentIndexChanged.connect(lambda _i: commit())
        elif isinstance(w, QPushButton) and field.kind == "color":
            def on_click():
                if self._target is None:
                    return
                from termin.editor.color_dialog import ColorDialog

                current_value = field.get_value(self._target)
                if current_value is None:
                    initial = (1.0, 1.0, 1.0, 1.0)
                elif isinstance(current_value, (list, tuple)) and len(current_value) >= 3:
                    r = float(current_value[0])
                    g = float(current_value[1])
                    b = float(current_value[2])
                    a = float(current_value[3]) if len(current_value) > 3 else 1.0
                    initial = (r, g, b, a)
                else:
                    initial = (1.0, 1.0, 1.0, 1.0)

                result = ColorDialog.get_color(initial, self)
                if result is None:
                    return
                new_color = QColor.fromRgbF(result[0], result[1], result[2], result[3])
                if hasattr(w, "_set_color"):
                    w._set_color(new_color)
                commit()

            w.clicked.connect(on_click)
        elif isinstance(w, QPushButton) and field.kind == "button":
            def on_button_click():
                if self._target is None:
                    return
                action = getattr(w, "_action", None)
                if action is not None:
                    action(self._target)

            w.clicked.connect(on_button_click)

    def _read_widget_value(self, w: QWidget, field: InspectField) -> Any:
        if isinstance(w, QDoubleSpinBox):
            val = w.value()
            return int(val) if field.kind == "int" else float(val)

        if isinstance(w, QCheckBox):
            return bool(w.isChecked())

        if isinstance(w, QLineEdit) and field.kind == "string":
            text = w.text()
            # Return None for empty strings if the field originally had None
            return text if text else None

        if hasattr(w, "_boxes"):
            return np.array([sb.value() for sb in w._boxes], dtype=float)

        if hasattr(w, "_slider") and field.kind == "slider":
            return float(w._slider.value())

        if isinstance(w, QComboBox) and field.kind == "material":
            if self._resources is None:
                return None
            name = w.currentText()
            if not name:
                return None
            return self._resources.get_material(name)

        if isinstance(w, QComboBox) and field.kind == "mesh":
            if self._resources is None:
                return None
            name = w.currentText()
            if not name:
                return None
            return self._resources.get_mesh(name)

        if isinstance(w, QComboBox) and field.kind == "voxel_grid":
            if self._resources is None:
                return None
            name = w.currentText()
            if not name:
                return None
            return self._resources.get_voxel_grid(name)

        if isinstance(w, QComboBox) and field.kind == "navmesh":
            name = w.currentText()
            if not name:
                return None
            # Возвращаем имя, а не объект — компонент сам получит navmesh по имени
            return name

        if isinstance(w, QComboBox) and field.kind == "enum":
            if field.choices:
                return w.currentData()
            text = w.currentText()
            return text if text else None

        if isinstance(w, QPushButton) and field.kind == "color":
            color_tuple = getattr(w, "_current_color", None)
            return color_tuple

        return None
