"""tcgui-версии виджетов редактирования полей для инспекторов.

Аналог termin/editor/widgets/field_widgets.py, но без зависимости на PyQt6.
Все виджеты компонуются из tcgui-примитивов.

Интерфейс намеренно повторяет Qt-версию:
    widget = FloatFieldWidget(min_val=0, max_val=1)
    widget.bind_field(key, field, target)
    widget.load_from_target()
"""

from __future__ import annotations

from typing import Any, Callable, Optional, TYPE_CHECKING

from tcbase import log
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.button import Button
from tcgui.widgets.checkbox import Checkbox
from tcgui.widgets.spin_box import SpinBox
from tcgui.widgets.slider import Slider
from tcgui.widgets.text_input import TextInput
from tcgui.widgets.combo_box import ComboBox
from tcgui.widgets.widget import Widget
from tcgui.widgets.units import px

if TYPE_CHECKING:
    from termin.inspect import InspectField
    from termin.assets.resources import ResourceManager


# ------------------------------------------------------------------
# Базовый класс
# ------------------------------------------------------------------

class FieldWidget(Widget):
    """Базовый класс для всех виджетов редактирования полей."""

    def __init__(self) -> None:
        super().__init__()
        self.on_value_changed: Callable[[], None] | None = None
        self._field_key: str = ""
        self._field: InspectField | None = None
        self._target: Any = None

    def bind_field(self, key: str, field: "InspectField", target: Any) -> None:
        self._field_key = key
        self._field = field
        self._target = target

    def full_row(self) -> bool:
        return False

    def get_value(self) -> Any:
        raise NotImplementedError

    def set_value(self, value: Any) -> None:
        raise NotImplementedError

    def load_from_target(self) -> None:
        if self._field is None or self._target is None:
            return
        self.set_value(self._field.get_value(self._target))

    def apply_to_target(self) -> tuple[Any, Any] | None:
        if self._field is None or self._target is None:
            return None
        old_value = self._field.get_value(self._target)
        new_value = self.get_value()
        self._field.set_value(self._target, new_value)
        return old_value, new_value

    def _emit(self) -> None:
        if self.on_value_changed is not None:
            self.on_value_changed()

    @staticmethod
    def _values_equal(a: Any, b: Any) -> bool:
        try:
            if isinstance(a, (tuple, list)) or isinstance(b, (tuple, list)):
                a_seq = list(a) if a is not None else []
                b_seq = list(b) if b is not None else []
                if len(a_seq) != len(b_seq):
                    return False
                return all(FieldWidget._values_equal(x, y) for x, y in zip(a_seq, b_seq))
            return a == b or str(a) == str(b)
        except Exception as e:
            log.debug(f"[FieldWidget] _values_equal comparison failed: {e}")
            return False

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        w = self.preferred_width.to_pixels(viewport_w) if self.preferred_width else 180.0
        h = 24.0
        return (w, h)

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float) -> None:
        super().layout(x, y, width, height, viewport_w, viewport_h)
        for child in self.children:
            child.layout(x, y, width, height, viewport_w, viewport_h)

    def render(self, renderer) -> None:
        for child in self.children:
            child.render(renderer)

    def hit_test(self, px: float, py: float):
        for child in reversed(self.children):
            hit = child.hit_test(px, py)
            if hit is not None:
                return hit
        return None


class InlineMaterialFieldWidget(FieldWidget):
    """Inline TcMaterial editor driven by inspect metadata."""

    def __init__(self, resources: "ResourceManager | None" = None) -> None:
        super().__init__()
        from termin.editor_tcgui.material_inspector import MaterialInspectorTcgui

        self._material = None
        self._inspector = MaterialInspectorTcgui(resources)
        self._inspector.on_changed = self._on_material_changed
        self.add_child(self._inspector)

    def set_scene_getter(self, getter: Callable[[], Any] | None) -> None:
        if getter is not None:
            self._inspector.set_scene_getter(getter)

    def _material_from_value(self, value: Any):
        if value is None:
            return None
        if isinstance(value, dict):
            uuid = value.get("uuid")
            if isinstance(uuid, str) and uuid:
                from termin._native.render import TcMaterial
                return TcMaterial.from_uuid(uuid)
            return None
        return value

    def _on_material_changed(self) -> None:
        self._emit()

    def get_value(self) -> Any:
        return self._material

    def set_value(self, value: Any) -> None:
        self._material = self._material_from_value(value)
        self._inspector.set_target(self._material, subtitle="")

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        return self._inspector.compute_size(viewport_w, viewport_h)

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float) -> None:
        Widget.layout(self, x, y, width, height, viewport_w, viewport_h)
        self._inspector.layout(x, y, width, height, viewport_w, viewport_h)


# ------------------------------------------------------------------
# Float / Int
# ------------------------------------------------------------------

class FloatFieldWidget(FieldWidget):
    """SpinBox для float/int полей."""

    def __init__(
        self,
        is_int: bool = False,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
        step: Optional[float] = None,
    ) -> None:
        super().__init__()
        self._is_int = is_int

        self._spinbox = SpinBox()
        self._spinbox.decimals = 0 if is_int else 4
        self._spinbox.min_value = min_val if min_val is not None else -1e9
        self._spinbox.max_value = max_val if max_val is not None else 1e9
        self._spinbox.preferred_width = px(92)
        if step is not None:
            self._spinbox.step = step
        self._spinbox.on_changed = self._on_changed
        self.add_child(self._spinbox)

    def _on_changed(self, _value: float) -> None:
        self._emit()

    def get_value(self) -> float | int:
        v = self._spinbox.value
        return int(v) if self._is_int else float(v)

    def set_value(self, value: Any) -> None:
        old = self._spinbox.on_changed
        self._spinbox.on_changed = None
        self._spinbox.value = float(value) if value is not None else 0.0
        self._spinbox.on_changed = old


# ------------------------------------------------------------------
# Bool
# ------------------------------------------------------------------

class BoolFieldWidget(FieldWidget):
    """Checkbox для bool полей."""

    def __init__(self) -> None:
        super().__init__()
        self._checkbox = Checkbox()
        self._checkbox.on_changed = self._on_changed
        self.add_child(self._checkbox)

    def _on_changed(self, _checked: bool) -> None:
        self._emit()

    def get_value(self) -> bool:
        return self._checkbox.checked

    def set_value(self, value: Any) -> None:
        old = self._checkbox.on_changed
        self._checkbox.on_changed = None
        self._checkbox.checked = bool(value) if value is not None else False
        self._checkbox.on_changed = old


# ------------------------------------------------------------------
# String
# ------------------------------------------------------------------

class StringFieldWidget(FieldWidget):
    """TextInput для строковых полей."""

    def __init__(self, read_only: bool = False) -> None:
        super().__init__()
        self._read_only = read_only
        self._input = TextInput()
        self._input.read_only = read_only
        self._input.focusable = not read_only
        if not read_only:
            self._input.on_changed = self._on_changed
        self.add_child(self._input)

    def _on_changed(self, _text: str) -> None:
        self._emit()

    def get_value(self) -> Optional[str]:
        text = self._input.text
        return text if text else None

    def set_value(self, value: Any) -> None:
        old = self._input.on_changed
        self._input.on_changed = None
        self._input.text = str(value) if value is not None else ""
        self._input.on_changed = old


# ------------------------------------------------------------------
# Vec3
# ------------------------------------------------------------------

class Vec3FieldWidget(FieldWidget):
    """3 SpinBox в ряд для vec3 полей."""

    def __init__(
        self,
        min_val: float = -1e9,
        max_val: float = 1e9,
        step: Optional[float] = None,
    ) -> None:
        super().__init__()
        self._boxes: list[SpinBox] = []

        self._row = HStack()
        self._row.spacing = 2
        self.add_child(self._row)

        for _ in range(3):
            sb = SpinBox()
            sb.decimals = 4
            sb.min_value = min_val
            sb.max_value = max_val
            sb.stretch = True
            if step is not None:
                sb.step = step
            sb.on_changed = self._on_changed
            self._row.add_child(sb)
            self._boxes.append(sb)

    def _on_changed(self, _value: float) -> None:
        self._emit()

    def get_value(self) -> list[float]:
        return [float(sb.value) for sb in self._boxes]

    def set_value(self, value: Any) -> None:
        if value is None:
            arr = [0.0, 0.0, 0.0]
        else:
            arr = list(value)

        for sb, v in zip(self._boxes, arr):
            old = sb.on_changed
            sb.on_changed = None
            sb.value = float(v)
            sb.on_changed = old

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float) -> None:
        super().layout(x, y, width, height, viewport_w, viewport_h)
        self._row.layout(x, y, width, height, viewport_w, viewport_h)

    def render(self, renderer) -> None:
        self._row.render(renderer)

    def hit_test(self, px: float, py: float):
        return self._row.hit_test(px, py)


# ------------------------------------------------------------------
# Slider (int)
# ------------------------------------------------------------------

class SliderFieldWidget(FieldWidget):
    """Slider + SpinBox для целочисленных диапазонов."""

    def __init__(self, min_val: int = 0, max_val: int = 100) -> None:
        super().__init__()
        self._min = min_val
        self._max = max_val

        self._row = HStack()
        self._row.spacing = 4
        self.add_child(self._row)

        self._slider = Slider()
        self._slider.min_value = float(min_val)
        self._slider.max_value = float(max_val)
        self._slider.on_changed = self._on_slider_changed

        self._spinbox = SpinBox()
        self._spinbox.decimals = 0
        self._spinbox.min_value = float(min_val)
        self._spinbox.max_value = float(max_val)
        self._spinbox.preferred_width = px(84)
        self._spinbox.on_changed = self._on_spin_changed

        self._slider.stretch = True
        self._row.add_child(self._slider)
        self._row.add_child(self._spinbox)
        self._syncing = False

    def _on_slider_changed(self, _value: float) -> None:
        if self._syncing:
            return
        self._syncing = True
        old = self._spinbox.on_changed
        self._spinbox.on_changed = None
        self._spinbox.value = self._slider.value
        self._spinbox.on_changed = old
        self._syncing = False
        self._emit()

    def _on_spin_changed(self, _value: float) -> None:
        if self._syncing:
            return
        self._syncing = True
        old = self._slider.on_changed
        self._slider.on_changed = None
        self._slider.value = self._spinbox.value
        self._slider.on_changed = old
        self._syncing = False
        self._emit()

    def get_value(self) -> int:
        return int(self._slider.value)

    def set_value(self, value: Any) -> None:
        v = float(int(value)) if value is not None else 0.0
        self._syncing = True
        old_sl = self._slider.on_changed
        old_sb = self._spinbox.on_changed
        self._slider.on_changed = None
        self._spinbox.on_changed = None
        self._slider.value = v
        self._spinbox.value = v
        self._slider.on_changed = old_sl
        self._spinbox.on_changed = old_sb
        self._syncing = False

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float) -> None:
        super().layout(x, y, width, height, viewport_w, viewport_h)
        self._row.layout(x, y, width, height, viewport_w, viewport_h)

    def render(self, renderer) -> None:
        self._row.render(renderer)

    def hit_test(self, px: float, py: float):
        return self._row.hit_test(px, py)


# ------------------------------------------------------------------
# Color
# ------------------------------------------------------------------

class ColorFieldWidget(FieldWidget):
    """Кнопка-свотч открывающая ColorDialog."""

    def __init__(self) -> None:
        super().__init__()
        self._color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)

        self._btn = Button()
        self._btn.text = self._color_label(self._color)
        self._btn.on_click = self._on_click
        self._btn.background_color = self._color
        self.add_child(self._btn)

    @staticmethod
    def _color_label(c: tuple) -> str:
        return f"{c[0]:.2f}, {c[1]:.2f}, {c[2]:.2f}, {c[3]:.2f}"

    def _on_click(self) -> None:
        try:
            from tcgui.widgets.color_dialog import show_color_dialog
            show_color_dialog(
                self._ui,
                initial_color=self._color,
                on_result=self._on_color_result,
            )
        except Exception as e:
            log.error(f"[ColorFieldWidget] Failed to open color dialog: {e}")

    def _on_color_result(self, color: tuple | None) -> None:
        if color is not None:
            self._color = color
            self._btn.text = self._color_label(color)
            self._btn.background_color = color
            self._emit()

    def get_value(self) -> tuple[float, float, float, float]:
        return self._color

    def set_value(self, value: Any) -> None:
        if value is None:
            self._color = (1.0, 1.0, 1.0, 1.0)
        elif isinstance(value, (list, tuple)) and len(value) >= 3:
            r, g, b = float(value[0]), float(value[1]), float(value[2])
            a = float(value[3]) if len(value) > 3 else 1.0
            self._color = (
                max(0.0, min(1.0, r)),
                max(0.0, min(1.0, g)),
                max(0.0, min(1.0, b)),
                max(0.0, min(1.0, a)),
            )
        self._btn.text = self._color_label(self._color)
        self._btn.background_color = self._color


# ------------------------------------------------------------------
# Button (action)
# ------------------------------------------------------------------

class ButtonFieldWidget(FieldWidget):
    """Кнопка, вызывающая action(target)."""

    def __init__(
        self,
        label: str = "Action",
    ) -> None:
        super().__init__()

        self._btn = Button()
        self._btn.text = label
        self._btn.on_click = self._on_click
        self.add_child(self._btn)

    def full_row(self) -> bool:
        return True

    def get_value(self) -> None:
        return None

    def set_value(self, value: Any) -> None:
        pass

    def load_from_target(self) -> None:
        pass

    def apply_to_target(self) -> tuple[Any, Any] | None:
        if self._field is not None and self._target is not None and self._field.action is not None:
            self._field.action(self._target)
        return None

    def _on_click(self) -> None:
        self._emit()


# ------------------------------------------------------------------
# Combo (enum)
# ------------------------------------------------------------------

class ComboFieldWidget(FieldWidget):
    """ComboBox для enum полей."""

    def __init__(
        self,
        choices: Optional[list[tuple[Any, str]]] = None,
    ) -> None:
        super().__init__()
        self._choices: list[tuple[Any, str]] = choices or []

        self._combo = ComboBox()
        for _value, label in self._choices:
            self._combo.add_item(label)
        self._combo.on_changed = self._on_changed
        self.add_child(self._combo)

    def _on_changed(self, _index: int, _text: str) -> None:
        self._emit()

    def get_value(self) -> Any:
        idx = self._combo.selected_index
        if self._choices and 0 <= idx < len(self._choices):
            return self._choices[idx][0]
        return self._combo.selected_text

    def set_value(self, value: Any) -> None:
        old = self._combo.on_changed
        self._combo.on_changed = None
        if self._choices:
            for i, (v, _) in enumerate(self._choices):
                if self._values_equal(v, value):
                    self._combo.selected_index = i
                    break
        else:
            text = str(value) if value is not None else ""
            for i in range(self._combo.item_count):
                if self._combo.item_text(i) == text:
                    self._combo.selected_index = i
                    break
        self._combo.on_changed = old


# ------------------------------------------------------------------
# AgentType
# ------------------------------------------------------------------

class AgentTypeFieldWidget(FieldWidget):
    """ComboBox с типами навигационных агентов из NavigationSettingsManager."""

    def __init__(self) -> None:
        super().__init__()
        self._combo = ComboBox()
        self._combo.on_changed = self._on_changed
        self.add_child(self._combo)
        self._refresh_choices()

    def _refresh_choices(self) -> None:
        old = self._combo.on_changed
        self._combo.on_changed = None
        current = self._combo.selected_text
        self._combo.clear()
        try:
            from termin.navmesh.settings import NavigationSettingsManager
            names = NavigationSettingsManager.instance().settings.get_agent_type_names()
            for name in names:
                self._combo.add_item(name)
        except Exception as e:
            log.debug(f"[AgentTypeFieldWidget] Failed to get agent types: {e}")
            self._combo.add_item("Human")
        if current:
            for i in range(self._combo.item_count):
                if self._combo.item_text(i) == current:
                    self._combo.selected_index = i
                    break
        self._combo.on_changed = old

    def _on_changed(self, _index: int, _text: str) -> None:
        self._emit()

    def get_value(self) -> str:
        return self._combo.selected_text or "Human"

    def set_value(self, value: Any) -> None:
        old = self._combo.on_changed
        self._combo.on_changed = None
        self._refresh_choices()
        text = str(value) if value else "Human"
        for i in range(self._combo.item_count):
            if self._combo.item_text(i) == text:
                self._combo.selected_index = i
                break
        self._combo.on_changed = old


# ------------------------------------------------------------------
# ClipSelector
# ------------------------------------------------------------------

class ClipSelectorWidget(FieldWidget):
    """ComboBox для выбора анимационного клипа из target-компонента."""

    def __init__(self) -> None:
        super().__init__()
        self._combo = ComboBox()
        self._combo.on_changed = self._on_changed
        self.add_child(self._combo)

    def bind_field(self, key: str, field: "InspectField", target: Any) -> None:
        super().bind_field(key, field, target)
        self._refresh_choices()

    def _refresh_choices(self) -> None:
        old = self._combo.on_changed
        self._combo.on_changed = None
        current = self._combo.selected_text
        self._combo.clear()
        self._combo.add_item("(none)")
        if self._target is not None:
            try:
                from termin._native.inspect import InspectRegistry
                clips = InspectRegistry.instance().get(self._target, "clips")
                if clips:
                    for item in sorted(clips, key=lambda x: x.get("name", "")):
                        name = item.get("name", "")
                        if name:
                            self._combo.add_item(name)
            except Exception as e:
                log.debug(f"[ClipSelectorWidget] Failed to get clips: {e}")
        for i in range(self._combo.item_count):
            if self._combo.item_text(i) == current:
                self._combo.selected_index = i
                break
        self._combo.on_changed = old

    def _on_changed(self, _index: int, _text: str) -> None:
        self._emit()

    def get_value(self) -> str:
        text = self._combo.selected_text
        return "" if text == "(none)" else (text or "")

    def set_value(self, value: Any) -> None:
        old = self._combo.on_changed
        self._combo.on_changed = None
        if self._target is not None:
            self._refresh_choices()
        text = str(value) if value else "(none)"
        for i in range(self._combo.item_count):
            if self._combo.item_text(i) == text:
                self._combo.selected_index = i
                break
        else:
            self._combo.selected_index = 0  # (none)
        self._combo.on_changed = old


# ------------------------------------------------------------------
# HandleSelector (ресурсы: material, mesh, texture, …)
# ------------------------------------------------------------------

class HandleSelectorWidget(FieldWidget):
    """ComboBox для выбора ресурса через HandleAccessors."""

    def __init__(
        self,
        resource_kind: str,
        resources: Optional["ResourceManager"] = None,
        allow_none: bool = True,
    ) -> None:
        super().__init__()
        self._resource_kind = resource_kind
        self._resources = resources
        self._allow_none = allow_none
        self._name_to_uuid: dict[str, Optional[str]] = {}
        self._uuid_to_name: dict[str, str] = {}

        self._combo = ComboBox()
        self._combo.on_changed = self._on_changed
        self.add_child(self._combo)
        self._refresh_items()

    def set_resources(self, resources: "ResourceManager") -> None:
        self._resources = resources
        self._refresh_items()

    def _get_accessors(self):
        if self._resources is None:
            return None
        return self._resources.get_handle_accessors(self._resource_kind)

    def _refresh_items(self) -> None:
        accessors = self._get_accessors()
        if accessors is None:
            return
        old = self._combo.on_changed
        self._combo.on_changed = None
        current = self._combo.selected_text
        self._combo.clear()
        self._name_to_uuid.clear()
        self._uuid_to_name.clear()
        if self._allow_none:
            self._combo.add_item("(None)")
        for name, uuid in accessors.list_items():
            self._combo.add_item(name)
            self._name_to_uuid[name] = uuid
            if uuid:
                self._uuid_to_name[uuid] = name
        for i in range(self._combo.item_count):
            if self._combo.item_text(i) == current:
                self._combo.selected_index = i
                break
        self._combo.on_changed = old

    def _on_changed(self, _index: int, _text: str) -> None:
        self._emit()

    def get_value(self) -> Optional[dict]:
        name = self._combo.selected_text
        if not name or name == "(None)":
            return None
        uuid = self._name_to_uuid.get(name)
        return {"uuid": uuid, "name": name}

    def set_value(self, value: Any) -> None:
        old = self._combo.on_changed
        self._combo.on_changed = None
        self._refresh_items()
        if value is None:
            self._combo.selected_index = 0 if self._allow_none else -1
            self._combo.on_changed = old
            return
        uuid = value.get("uuid") if isinstance(value, dict) else None
        name = value.get("name") if isinstance(value, dict) else None
        if uuid and uuid in self._uuid_to_name:
            name = self._uuid_to_name[uuid]
        if name:
            for i in range(self._combo.item_count):
                if self._combo.item_text(i) == name:
                    self._combo.selected_index = i
                    self._combo.on_changed = old
                    return
            log.warn(f"[HandleSelectorWidget] {self._resource_kind}: '{name}' not found")
        self._combo.selected_index = 0 if self._allow_none else -1
        self._combo.on_changed = old


# ------------------------------------------------------------------
# FieldWidgetFactory
# ------------------------------------------------------------------

class FieldWidgetFactory:
    """Создаёт нужный FieldWidget по типу InspectField."""

    def __init__(self, resources: Optional["ResourceManager"] = None) -> None:
        self._resources = resources
        self._scene_getter: Optional[Callable[[], Any]] = None

    def set_resources(self, resources: "ResourceManager") -> None:
        self._resources = resources

    def set_scene_getter(self, getter: Callable[[], Any]) -> None:
        self._scene_getter = getter

    def create(self, field: "InspectField", metadata: dict[str, Any] | None = None) -> FieldWidget:
        kind = field.kind
        metadata = metadata or field.metadata or {}
        widget_kind = metadata.get("widget")

        if widget_kind in ("inline_material", "material_inline") and kind == "tc_material":
            widget = InlineMaterialFieldWidget(self._resources)
            widget.set_scene_getter(self._scene_getter)
            return widget

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
            )

        if kind in ("enum", "combo"):
            return ComboFieldWidget(choices=field.choices)

        if kind == "clip_selector":
            return ClipSelectorWidget()

        if kind == "agent_type":
            return AgentTypeFieldWidget()

        if kind in (
            "tc_material", "mesh_handle", "tc_mesh",
            "skeleton_handle", "tc_skeleton",
            "voxel_grid_handle", "navmesh_handle",
            "texture_handle", "ui_handle",
        ):
            return HandleSelectorWidget(
                resource_kind=kind,
                resources=self._resources,
                allow_none=True,
            )

        if kind == "audio_clip_handle":
            # Пока fallback; специализированный виджет будет добавлен отдельно
            return HandleSelectorWidget(
                resource_kind="audio_clip_handle",
                resources=self._resources,
                allow_none=True,
            )

        if kind == "layer_mask":
            from termin.editor_tcgui.widgets.layer_mask_widget import LayerMaskFieldWidget
            return LayerMaskFieldWidget(scene_getter=self._scene_getter)

        # Fallback: read-only строка
        log.debug(f"[FieldWidgetFactory] Unknown field kind '{kind}', using StringFieldWidget")
        return StringFieldWidget(read_only=True)
