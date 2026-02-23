"""
Typed field widgets for inspector panels.

This module provides a set of typed widgets for editing fields in inspector panels,
replacing the previous approach with hasattr/getattr dynamic attribute access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Optional, List

from tcbase import log

from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QCheckBox,
    QLineEdit,
    QComboBox,
    QPushButton,
    QSlider,
)
from termin.editor.widgets.spinbox import DoubleSpinBox, SpinBox
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
    - sequence-like objects
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
        seq = list(value)
        if len(seq) >= 3:
            r = float(seq[0])
            g = float(seq[1])
            b = float(seq[2])
            a = float(seq[3]) if len(seq) > 3 else 1.0
            return QColor.fromRgbF(
                max(0.0, min(1.0, r)),
                max(0.0, min(1.0, g)),
                max(0.0, min(1.0, b)),
                max(0.0, min(1.0, a)),
            )
    except Exception:
        log.debug(f"[field_widgets] array_to_qcolor failed for value type {type(value)}")
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

    @staticmethod
    def _values_equal(a: Any, b: Any) -> bool:
        """Safe comparison for scalars and sequence-like values."""
        try:
            a_seq = list(a) if isinstance(a, (tuple, list)) else None
            b_seq = list(b) if isinstance(b, (tuple, list)) else None
            if a_seq is None:
                try:
                    a_seq = list(a)
                except Exception:
                    a_seq = None
            if b_seq is None:
                try:
                    b_seq = list(b)
                except Exception:
                    b_seq = None
            if a_seq is not None or b_seq is not None:
                if a_seq is None:
                    a_seq = [a]
                if b_seq is None:
                    b_seq = [b]
                if len(a_seq) != len(b_seq):
                    return False
                return all(FieldWidget._values_equal(x, y) for x, y in zip(a_seq, b_seq))
            if a == b:
                return True
            # Fallback: compare as strings (for enum choices where value is "1" but field is int 1)
            return str(a) == str(b)
        except Exception:
            log.debug(f"[field_widgets] _values_equal failed comparing {type(a)} and {type(b)}")
            return False


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

        self._spinbox = DoubleSpinBox()
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

    value_changed = pyqtSignal()  # Переопределяем сигнал явно

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
            self._line_edit.textEdited.connect(self._on_text_changed)
            self._line_edit.editingFinished.connect(self._on_editing_finished)
        layout.addWidget(self._line_edit)

    def _on_text_changed(self, text: str) -> None:
        self.value_changed.emit()

    def _on_editing_finished(self) -> None:
        self.value_changed.emit()

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

        self._boxes: list[DoubleSpinBox] = []
        for _ in range(3):
            sb = DoubleSpinBox()
            sb.setDecimals(4)
            sb.setRange(min_val, max_val)
            if step is not None:
                sb.setSingleStep(step)
            sb.valueChanged.connect(self.value_changed.emit)
            layout.addWidget(sb)
            self._boxes.append(sb)

    def get_value(self) -> list[float]:
        return [float(sb.value()) for sb in self._boxes]

    def set_value(self, value: Any) -> None:
        if value is not None:
            arr = list(value)
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

        self._spinbox = SpinBox()
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
            try:
                self._action(self._target)
            except Exception as e:
                from tcbase import log
                log.error(f"Button action failed: {e}")


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


class AgentTypeFieldWidget(FieldWidget):
    """Widget for selecting navigation agent type from NavigationSettingsManager."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._combo = QComboBox()
        self._combo.currentIndexChanged.connect(lambda _: self.value_changed.emit())
        layout.addWidget(self._combo)

        self._refresh_choices()

    def _refresh_choices(self) -> None:
        """Refresh dropdown options from NavigationSettingsManager."""
        self._combo.blockSignals(True)
        current = self._combo.currentText()
        self._combo.clear()

        try:
            from termin.navmesh.settings import NavigationSettingsManager
            manager = NavigationSettingsManager.instance()
            names = manager.settings.get_agent_type_names()
            for name in names:
                self._combo.addItem(name)
        except Exception as e:
            log.debug(f"[AgentTypeFieldWidget] Failed to get agent types: {e}")
            self._combo.addItem("Human")  # Default fallback

        # Restore selection
        idx = self._combo.findText(current)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)
        elif self._combo.count() > 0:
            self._combo.setCurrentIndex(0)

        self._combo.blockSignals(False)

    def get_value(self) -> str:
        return self._combo.currentText()

    def set_value(self, value: Any) -> None:
        self._combo.blockSignals(True)
        self._refresh_choices()

        value_str = str(value) if value else "Human"
        idx = self._combo.findText(value_str)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)
        elif self._combo.count() > 0:
            self._combo.setCurrentIndex(0)
        self._combo.blockSignals(False)


class ClipSelectorWidget(FieldWidget):
    """Widget for selecting animation clip from available clips."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._target: Any = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._combo = QComboBox()
        self._combo.currentIndexChanged.connect(lambda _: self.value_changed.emit())
        layout.addWidget(self._combo)

    def set_target(self, target: Any) -> None:
        """Set target component to read available clips from."""
        self._target = target
        self._refresh_choices()

    def _refresh_choices(self) -> None:
        """Refresh dropdown options from target's clips."""
        self._combo.blockSignals(True)
        current = self._combo.currentText()
        self._combo.clear()

        # Add empty option
        self._combo.addItem("(none)", userData="")

        if self._target is not None:
            # Get clips from InspectRegistry (serialized list of dicts)
            from termin._native.inspect import InspectRegistry
            clips = InspectRegistry.instance().get(self._target, "clips")
            if clips:
                names = sorted(item.get("name", "") for item in clips if item.get("name"))
                for name in names:
                    self._combo.addItem(name, userData=name)

        # Restore selection
        idx = self._combo.findData(current)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)

        self._combo.blockSignals(False)

    def get_value(self) -> str:
        return self._combo.currentData() or ""

    def set_value(self, value: Any) -> None:
        self._combo.blockSignals(True)
        # Refresh in case clips changed
        if self._target is not None:
            self._refresh_choices()

        value_str = str(value) if value else ""
        idx = self._combo.findData(value_str)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)
        else:
            self._combo.setCurrentIndex(0)  # (none)
        self._combo.blockSignals(False)


class HandleSelectorWidget(FieldWidget):
    """
    Unified widget for selecting resources via Handle pattern.

    Works with any resource type that has HandleAccessors registered
    in ResourceManager (material, mesh, audio_clip, voxel_grid, navmesh, skeleton, texture).

    Values are dict format: {"uuid": "...", "name": "..."}
    """

    def __init__(
        self,
        resource_kind: str,
        resources: Optional["ResourceManager"] = None,
        allow_none: bool = True,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._resource_kind = resource_kind
        self._resources = resources
        self._allow_none = allow_none
        self._name_to_uuid: dict[str, Optional[str]] = {}
        self._uuid_to_name: dict[str, str] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._combo = QComboBox()
        self._combo.currentIndexChanged.connect(lambda _: self.value_changed.emit())
        layout.addWidget(self._combo)

        self._refresh_items()

    def set_resources(self, resources: "ResourceManager") -> None:
        self._resources = resources
        self._refresh_items()

    def _get_accessors(self):
        """Get HandleAccessors for this resource kind."""
        if self._resources is None:
            return None
        return self._resources.get_handle_accessors(self._resource_kind)

    def _refresh_items(self) -> None:
        accessors = self._get_accessors()
        if accessors is None:
            return

        self._combo.blockSignals(True)
        current_text = self._combo.currentText()
        self._combo.clear()
        self._name_to_uuid.clear()
        self._uuid_to_name.clear()

        # Add (None) option if allowed
        if self._allow_none:
            self._combo.addItem("(None)", userData=None)

        # Get items with UUIDs
        items = accessors.list_items()
        for name, uuid in items:
            self._combo.addItem(name, userData=name)
            self._name_to_uuid[name] = uuid
            if uuid:
                self._uuid_to_name[uuid] = name

        # Restore selection
        idx = self._combo.findText(current_text)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)
        elif self._allow_none:
            self._combo.setCurrentIndex(0)  # (None)

        self._combo.blockSignals(False)

    def get_value(self) -> Optional[dict]:
        """Get currently selected value as dict {"uuid": ..., "name": ...}."""
        name = self._combo.currentData()
        if not name:
            return None

        uuid = self._name_to_uuid.get(name)
        return {"uuid": uuid, "name": name}

    def set_value(self, value: Any) -> None:
        """Set widget value from dict {"uuid": ..., "name": ...}."""
        self._combo.blockSignals(True)

        # Refresh items in case the list changed
        self._refresh_items()

        if value is None:
            if self._allow_none:
                self._combo.setCurrentIndex(0)  # (None)
            else:
                self._combo.setCurrentIndex(-1)
            self._combo.blockSignals(False)
            return

        # Extract uuid and name from dict
        uuid = None
        name = None
        if isinstance(value, dict):
            uuid = value.get("uuid")
            name = value.get("name")
        else:
            # Legacy: try to get name from object via accessors
            accessors = self._get_accessors()
            if accessors is not None:
                name = accessors.find_name(value)

        # First try to find by UUID (more reliable than name)
        if uuid and uuid in self._uuid_to_name:
            list_name = self._uuid_to_name[uuid]
            idx = self._combo.findText(list_name)
            if idx >= 0:
                self._combo.setCurrentIndex(idx)
                self._combo.blockSignals(False)
                return

        # Fallback to name
        if name is not None:
            idx = self._combo.findText(name)
            if idx >= 0:
                self._combo.setCurrentIndex(idx)
                self._combo.blockSignals(False)
                return
            # Name not found - log warning
            log.warn(f"[HandleSelectorWidget] {self._resource_kind}: resource not found - name='{name}' uuid='{uuid}'")

        # Not found - set to (None) or -1
        if self._allow_none:
            self._combo.setCurrentIndex(0)  # (None)
        else:
            self._combo.setCurrentIndex(-1)

        self._combo.blockSignals(False)


class FieldWidgetFactory:
    """Factory for creating field widgets based on InspectField."""

    def __init__(self, resources: Optional["ResourceManager"] = None):
        self._resources = resources
        self._scene_getter: Optional[Callable[[], Any]] = None

    def set_resources(self, resources: "ResourceManager") -> None:
        self._resources = resources

    def set_scene_getter(self, getter: Callable[[], Any]) -> None:
        """Set callback for getting current scene (for layer_mask widget)."""
        self._scene_getter = getter

    def create(self, field: "InspectField") -> FieldWidget:
        """Create a widget for the given field."""
        kind = field.kind

        # If field has choices, use combo widget regardless of kind
        if field.choices:
            return ComboFieldWidget(choices=field.choices)

        if kind in ("float", "int", "double"):
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

        if kind == "clip_selector":
            return ClipSelectorWidget()

        if kind == "agent_type":
            return AgentTypeFieldWidget()

        # Handle-based resource selectors
        if kind in (
            "tc_material",
            "mesh_handle",
            "tc_mesh",
            "skeleton_handle",
            "tc_skeleton",
            "voxel_grid_handle",
            "navmesh_handle",
            "texture_handle",
            "ui_handle",
        ):
            return HandleSelectorWidget(
                resource_kind=kind,
                resources=self._resources,
                allow_none=True,
            )

        if kind == "audio_clip_handle":
            from termin.editor.widgets.audio_clip_widget import AudioClipFieldWidget

            return AudioClipFieldWidget(resources=self._resources)

        if kind == "vec3_list" or kind == "list[vec3]":
            from termin.editor.widgets.vec3_list_widget import Vec3ListWidget

            return Vec3ListWidget()

        if kind == "entity_list" or kind == "list[entity]":
            from termin.editor.widgets.entity_list_widget import EntityListWidget

            return EntityListWidget(
                read_only=field.read_only,
                scene_getter=self._scene_getter,
            )

        if kind in ("animation_clip_handle_list", "list[animation_clip_handle]", "list[tc_animation_clip]"):
            from termin.editor.widgets.generic_list_widget import GenericListWidget

            def get_clip_name(item: dict) -> str:
                # item is serialized dict: {"uuid": "...", "name": "...", "type": "...", "path": "..."}
                return item.get("name", "<unnamed>")

            return GenericListWidget(
                get_item_name=get_clip_name,
                item_type_label="clip",
                read_only=field.read_only,
            )

        if kind == "layer_mask":
            from termin.editor.widgets.layer_mask_widget import LayerMaskFieldWidget

            return LayerMaskFieldWidget(scene_getter=self._scene_getter)

        if kind == "pipeline_selector":
            from termin.editor.widgets.pipeline_selector_widget import PipelineSelectorWidget

            return PipelineSelectorWidget(resources=self._resources)

        # Fallback: read-only string
        return StringFieldWidget(read_only=True)
