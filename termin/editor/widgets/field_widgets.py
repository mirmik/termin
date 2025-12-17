"""
Typed field widgets for inspector panels.

This module provides a set of typed widgets for editing fields in inspector panels,
replacing the previous approach with hasattr/getattr dynamic attribute access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Optional

import numpy as np
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QDoubleSpinBox,
    QCheckBox,
    QLineEdit,
    QComboBox,
    QPushButton,
    QSlider,
    QSpinBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

if TYPE_CHECKING:
    from termin.editor.inspect_field import InspectField
    from termin.visualization.core.resources import ResourceManager


def to_qcolor(value: Any) -> QColor:
    """
    Convert color value to QColor.

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


class FieldWidget(QWidget):
    """Base class for all inspector field widgets."""

    value_changed = pyqtSignal()

    def get_value(self) -> Any:
        """Get current widget value."""
        raise NotImplementedError

    def set_value(self, value: Any) -> None:
        """Set widget value."""
        raise NotImplementedError


class FloatFieldWidget(FieldWidget):
    """Widget for float/int fields using QDoubleSpinBox."""

    def __init__(
        self,
        is_int: bool = False,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
        step: Optional[float] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._is_int = is_int

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._spinbox = QDoubleSpinBox()
        self._spinbox.setDecimals(0 if is_int else 4)
        self._spinbox.setRange(
            min_val if min_val is not None else -1e9,
            max_val if max_val is not None else 1e9,
        )
        if step is not None:
            self._spinbox.setSingleStep(step)
        self._spinbox.valueChanged.connect(self.value_changed.emit)
        layout.addWidget(self._spinbox)

    def get_value(self) -> float | int:
        val = self._spinbox.value()
        return int(val) if self._is_int else float(val)

    def set_value(self, value: Any) -> None:
        self._spinbox.blockSignals(True)
        self._spinbox.setValue(float(value) if value is not None else 0.0)
        self._spinbox.blockSignals(False)


class BoolFieldWidget(FieldWidget):
    """Widget for bool fields using QCheckBox."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._checkbox = QCheckBox()
        self._checkbox.stateChanged.connect(lambda _: self.value_changed.emit())
        layout.addWidget(self._checkbox)

    def get_value(self) -> bool:
        return self._checkbox.isChecked()

    def set_value(self, value: Any) -> None:
        self._checkbox.blockSignals(True)
        self._checkbox.setChecked(bool(value) if value is not None else False)
        self._checkbox.blockSignals(False)


class StringFieldWidget(FieldWidget):
    """Widget for string fields using QLineEdit."""

    def __init__(
        self,
        read_only: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._read_only = read_only

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._line_edit = QLineEdit()
        self._line_edit.setReadOnly(read_only)
        if not read_only:
            self._line_edit.textEdited.connect(lambda _: self.value_changed.emit())
            self._line_edit.editingFinished.connect(self.value_changed.emit)
        layout.addWidget(self._line_edit)

    def get_value(self) -> Optional[str]:
        text = self._line_edit.text()
        return text if text else None

    def set_value(self, value: Any) -> None:
        self._line_edit.blockSignals(True)
        self._line_edit.setText(str(value) if value is not None else "")
        self._line_edit.blockSignals(False)


class Vec3FieldWidget(FieldWidget):
    """Widget for vec3 fields using 3 QDoubleSpinBoxes."""

    def __init__(
        self,
        min_val: float = -1e9,
        max_val: float = 1e9,
        step: Optional[float] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._boxes: list[QDoubleSpinBox] = []
        for _ in range(3):
            sb = QDoubleSpinBox()
            sb.setDecimals(4)
            sb.setRange(min_val, max_val)
            if step is not None:
                sb.setSingleStep(step)
            sb.valueChanged.connect(self.value_changed.emit)
            layout.addWidget(sb)
            self._boxes.append(sb)

    def get_value(self) -> np.ndarray:
        return np.array([sb.value() for sb in self._boxes], dtype=float)

    def set_value(self, value: Any) -> None:
        if value is not None:
            arr = np.asarray(value).reshape(-1)
            for sb, v in zip(self._boxes, arr):
                sb.blockSignals(True)
                sb.setValue(float(v))
                sb.blockSignals(False)
        else:
            for sb in self._boxes:
                sb.blockSignals(True)
                sb.setValue(0.0)
                sb.blockSignals(False)


class SliderFieldWidget(FieldWidget):
    """Widget for slider fields using QSlider + QSpinBox."""

    def __init__(
        self,
        min_val: int = 0,
        max_val: int = 100,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(min_val, max_val)
        self._slider.setTickPosition(QSlider.TickPosition.NoTicks)

        self._spinbox = QSpinBox()
        self._spinbox.setRange(min_val, max_val)
        self._spinbox.setFixedWidth(50)

        # Sync slider and spinbox
        self._slider.valueChanged.connect(self._spinbox.setValue)
        self._spinbox.valueChanged.connect(self._slider.setValue)
        self._slider.valueChanged.connect(self.value_changed.emit)

        layout.addWidget(self._slider, stretch=1)
        layout.addWidget(self._spinbox)

    def get_value(self) -> int:
        return self._slider.value()

    def set_value(self, value: Any) -> None:
        int_val = int(value) if value is not None else 0
        self._slider.blockSignals(True)
        self._spinbox.blockSignals(True)
        self._slider.setValue(int_val)
        self._spinbox.setValue(int_val)
        self._slider.blockSignals(False)
        self._spinbox.blockSignals(False)


class ColorFieldWidget(FieldWidget):
    """Widget for color fields using QPushButton with color dialog."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._btn = QPushButton()
        self._btn.setAutoFillBackground(True)
        self._btn.clicked.connect(self._on_click)
        layout.addWidget(self._btn)

        self._color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)
        self._update_button_appearance()

    def get_value(self) -> tuple[float, float, float, float]:
        return self._color

    def set_value(self, value: Any) -> None:
        if value is None:
            self._color = (1.0, 1.0, 1.0, 1.0)
        else:
            qcol = to_qcolor(value)
            self._color = (qcol.redF(), qcol.greenF(), qcol.blueF(), qcol.alphaF())
        self._update_button_appearance()

    def _update_button_appearance(self) -> None:
        r, g, b, a = self._color
        qcol = QColor.fromRgbF(r, g, b, a)
        pal = self._btn.palette()
        pal.setColor(self._btn.backgroundRole(), qcol)
        self._btn.setPalette(pal)
        self._btn.setText(f"{r:.2f}, {g:.2f}, {b:.2f}, {a:.2f}")

    def _on_click(self) -> None:
        from termin.editor.color_dialog import ColorDialog

        result = ColorDialog.get_color(self._color, self)
        if result is not None:
            self._color = result
            self._update_button_appearance()
            self.value_changed.emit()


class ButtonFieldWidget(FieldWidget):
    """Widget for button fields that trigger actions."""

    def __init__(
        self,
        label: str = "Action",
        action: Optional[Callable] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._action = action
        self._target: Any = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._btn = QPushButton(label)
        self._btn.clicked.connect(self._on_click)
        layout.addWidget(self._btn)

    def set_target(self, target: Any) -> None:
        """Set the target object for the action callback."""
        self._target = target

    def get_value(self) -> None:
        return None

    def set_value(self, value: Any) -> None:
        pass

    def _on_click(self) -> None:
        if self._action is not None and self._target is not None:
            self._action(self._target)


class ComboFieldWidget(FieldWidget):
    """Widget for enum fields using QComboBox."""

    def __init__(
        self,
        choices: Optional[list[tuple[Any, str]]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._choices = choices or []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._combo = QComboBox()
        for value, label in self._choices:
            self._combo.addItem(label, userData=value)
        self._combo.currentIndexChanged.connect(lambda _: self.value_changed.emit())
        layout.addWidget(self._combo)

    def get_value(self) -> Any:
        if self._choices:
            return self._combo.currentData()
        text = self._combo.currentText()
        return text if text else None

    def set_value(self, value: Any) -> None:
        self._combo.blockSignals(True)
        if self._choices:
            for i in range(self._combo.count()):
                item_data = self._combo.itemData(i)
                if self._values_equal(item_data, value):
                    self._combo.setCurrentIndex(i)
                    self._combo.blockSignals(False)
                    return
            self._combo.setCurrentIndex(-1)
        else:
            idx = self._combo.findText(str(value) if value is not None else "")
            self._combo.setCurrentIndex(idx if idx >= 0 else -1)
        self._combo.blockSignals(False)

    @staticmethod
    def _values_equal(a: Any, b: Any) -> bool:
        """Safe comparison that handles numpy arrays."""
        try:
            if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
                a_arr = np.asarray(a)
                b_arr = np.asarray(b)
                if a_arr.shape != b_arr.shape:
                    return False
                return bool(np.allclose(a_arr, b_arr))
            if isinstance(a, (tuple, list)) and isinstance(b, (tuple, list)):
                if len(a) != len(b):
                    return False
                return all(ComboFieldWidget._values_equal(x, y) for x, y in zip(a, b))
            return a == b
        except Exception:
            return False


class ResourceComboWidget(FieldWidget):
    """Widget for resource fields (material, mesh, voxel_grid, navmesh)."""

    def __init__(
        self,
        resource_kind: str,
        resources: Optional["ResourceManager"] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._resource_kind = resource_kind
        self._resources = resources

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._combo = QComboBox()
        self._combo.currentIndexChanged.connect(lambda _: self.value_changed.emit())
        layout.addWidget(self._combo)

        self._refresh_items()

    def set_resources(self, resources: "ResourceManager") -> None:
        self._resources = resources
        self._refresh_items()

    def _refresh_items(self) -> None:
        if self._resources is None:
            return

        self._combo.blockSignals(True)
        current_text = self._combo.currentText()
        self._combo.clear()

        names = self._get_resource_names()
        for name in names:
            self._combo.addItem(name)

        # Restore selection
        idx = self._combo.findText(current_text)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)

        self._combo.blockSignals(False)

    def _get_resource_names(self) -> list[str]:
        if self._resources is None:
            return []
        if self._resource_kind == "material":
            return self._resources.list_material_names()
        if self._resource_kind == "mesh":
            return self._resources.list_mesh_names()
        if self._resource_kind == "voxel_grid":
            return self._resources.list_voxel_grid_names()
        if self._resource_kind == "navmesh":
            return self._resources.list_navmesh_names()
        return []

    def _find_resource_name(self, resource: Any) -> Optional[str]:
        if self._resources is None or resource is None:
            return None
        if self._resource_kind == "material":
            return self._resources.find_material_name(resource)
        if self._resource_kind == "mesh":
            return self._resources.find_mesh_name(resource)
        if self._resource_kind == "voxel_grid":
            return self._resources.find_voxel_grid_name(resource)
        if self._resource_kind == "navmesh":
            # navmesh is stored by name directly
            return resource if isinstance(resource, str) else None
        return None

    def _get_resource(self, name: str) -> Any:
        if self._resources is None or not name:
            return None
        if self._resource_kind == "material":
            return self._resources.get_material(name)
        if self._resource_kind == "mesh":
            return self._resources.get_mesh(name)
        if self._resource_kind == "voxel_grid":
            return self._resources.get_voxel_grid(name)
        if self._resource_kind == "navmesh":
            return self._resources.get_navmesh(name)
        return None

    def get_value(self) -> Any:
        name = self._combo.currentText()
        if not name:
            return None
        return self._get_resource(name)

    def set_value(self, value: Any) -> None:
        self._combo.blockSignals(True)

        # Refresh items in case the list changed
        self._refresh_items()

        if value is None:
            self._combo.setCurrentIndex(-1)
            self._combo.blockSignals(False)
            return

        name = self._find_resource_name(value)
        if name is None:
            self._combo.setCurrentIndex(-1)
        else:
            idx = self._combo.findText(name)
            self._combo.setCurrentIndex(idx if idx >= 0 else -1)

        self._combo.blockSignals(False)


class FieldWidgetFactory:
    """Factory for creating field widgets based on InspectField."""

    def __init__(self, resources: Optional["ResourceManager"] = None):
        self._resources = resources

    def set_resources(self, resources: "ResourceManager") -> None:
        self._resources = resources

    def create(self, field: "InspectField") -> FieldWidget:
        """Create a widget for the given field."""
        kind = field.kind

        if kind in ("float", "int"):
            return FloatFieldWidget(
                is_int=(kind == "int"),
                min_val=field.min,
                max_val=field.max,
                step=field.step,
            )

        if kind == "bool":
            return BoolFieldWidget()

        if kind == "string":
            read_only = (
                field.getter is not None
                and field.setter is None
                and field.path is None
            )
            return StringFieldWidget(read_only=read_only)

        if kind == "vec3":
            return Vec3FieldWidget(
                min_val=field.min if field.min is not None else -1e9,
                max_val=field.max if field.max is not None else 1e9,
                step=field.step,
            )

        if kind == "slider":
            return SliderFieldWidget(
                min_val=int(field.min) if field.min is not None else 0,
                max_val=int(field.max) if field.max is not None else 100,
            )

        if kind == "color":
            return ColorFieldWidget()

        if kind == "button":
            return ButtonFieldWidget(
                label=field.label or "Action",
                action=field.action,
            )

        if kind == "enum":
            return ComboFieldWidget(choices=field.choices)

        if kind in ("material", "mesh", "voxel_grid", "navmesh"):
            return ResourceComboWidget(
                resource_kind=kind,
                resources=self._resources,
            )

        if kind == "vec3_list":
            from termin.editor.widgets.vec3_list_widget import Vec3ListWidget

            return Vec3ListWidget()

        if kind == "entity_list":
            from termin.editor.widgets.entity_list_widget import EntityListWidget

            return EntityListWidget(read_only=field.read_only)

        # Fallback: read-only string
        return StringFieldWidget(read_only=True)
