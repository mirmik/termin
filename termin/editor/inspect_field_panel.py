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
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.core.resources import ResourceManager


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

        fields = getattr(target.__class__, "inspect_fields", None)
        if not fields:
            return

        self._fields = fields

        self._updating_from_model = True
        try:
            for key, field in fields.items():
                label = field.label or key
                widget = self._create_widget_for_field(field)
                self._widgets[key] = widget
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
            if value is None or self._resources is None:
                w.setCurrentIndex(-1)
                return
            name = self._resources.find_mesh_name(value)
            if name is None:
                w.setCurrentIndex(-1)
                return
            idx = w.findText(name)
            w.setCurrentIndex(idx if idx >= 0 else -1)
            return

        if isinstance(w, QComboBox) and field.kind == "enum":
            if field.choices:
                for i in range(w.count()):
                    if w.itemData(i) == value:
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
            w.editingFinished.connect(commit)
        elif hasattr(w, "_boxes"):
            for sb in w._boxes:
                sb.valueChanged.connect(lambda _v: commit())
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

        if isinstance(w, QComboBox) and field.kind == "enum":
            if field.choices:
                return w.currentData()
            text = w.currentText()
            return text if text else None

        if isinstance(w, QPushButton) and field.kind == "color":
            color_tuple = getattr(w, "_current_color", None)
            return color_tuple

        return None
