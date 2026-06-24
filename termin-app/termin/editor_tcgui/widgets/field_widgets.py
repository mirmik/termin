"""tcgui widgets for inspector field editing.

Все виджеты компонуются из tcgui-примитивов.

Интерфейс:
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
from tcgui.widgets.list_widget import ListWidget
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
                return all(FieldWidget._values_equal(x, y) for x, y in zip(a_seq, b_seq, strict=True))
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
                from termin.materials import TcMaterial
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

        for sb, v in zip(self._boxes, arr, strict=True):
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


class Vec3ListFieldWidget(FieldWidget):
    """Editable full-row table for list[vec3] fields."""

    def __init__(
        self,
        min_val: float = -1e9,
        max_val: float = 1e9,
        step: Optional[float] = None,
    ) -> None:
        super().__init__()
        self._min_val = min_val
        self._max_val = max_val
        self._step = step
        self._value: list[list[float]] = []
        self._label_prefix: str = "Positions"
        self._point_rows: list[tuple[Label, SpinBox, SpinBox, SpinBox, Button, Button]] = []

        self._header = Label()
        self._header.color = (0.72, 0.76, 0.84, 1.0)
        self.add_child(self._header)

        self._add_btn = Button()
        self._add_btn.text = "Add Point"
        self._add_btn.on_click = self._add_point
        self.add_child(self._add_btn)

    def bind_field(self, key: str, field: "InspectField", target: Any) -> None:
        super().bind_field(key, field, target)
        self._label_prefix = field.label or key

    def full_row(self) -> bool:
        return True

    def get_value(self) -> list[list[float]]:
        return [[point[0], point[1], point[2]] for point in self._value]

    def set_value(self, value: Any) -> None:
        self._value = self._coerce_points(value)
        self._rebuild_rows()

    def _coerce_points(self, value: Any) -> list[list[float]]:
        if value is None:
            return []
        if not isinstance(value, (list, tuple)):
            try:
                value = list(value)
            except Exception as e:
                log.error(f"[Vec3ListFieldWidget] invalid points value: {e}")
                return []

        points: list[list[float]] = []
        for index, item in enumerate(value):
            try:
                components = list(item)
                if len(components) < 3:
                    log.error(
                        "[Vec3ListFieldWidget] point "
                        f"{index} has {len(components)} components, expected 3"
                    )
                    points.append([0.0, 0.0, 0.0])
                    continue
                points.append([
                    float(components[0]),
                    float(components[1]),
                    float(components[2]),
                ])
            except Exception as e:
                log.error(f"[Vec3ListFieldWidget] invalid point {index}: {e}")
                points.append([0.0, 0.0, 0.0])
        return points

    def _make_spinbox(self, row_index: int, component_index: int, value: float) -> SpinBox:
        spinbox = SpinBox()
        spinbox.decimals = 4
        spinbox.min_value = self._min_val
        spinbox.max_value = self._max_val
        if self._step is not None:
            spinbox.step = self._step
        spinbox.value = value
        spinbox.on_changed = (
            lambda new_value, r=row_index, c=component_index:
                self._set_point_component(r, c, new_value)
        )
        return spinbox

    def _rebuild_rows(self) -> None:
        for row in self._point_rows:
            for widget in row:
                self.remove_child(widget)
        self._point_rows.clear()

        count = len(self._value)
        item_label = "point" if count == 1 else "points"
        self._header.text = f"{self._label_prefix}: {count} {item_label}"

        for row_index, point in enumerate(self._value):
            index_label = Label()
            index_label.text = str(row_index)
            index_label.color = (0.55, 0.60, 0.68, 1.0)

            x_box = self._make_spinbox(row_index, 0, point[0])
            y_box = self._make_spinbox(row_index, 1, point[1])
            z_box = self._make_spinbox(row_index, 2, point[2])

            insert_btn = Button()
            insert_btn.text = "+"
            insert_btn.tooltip = "Insert point after this row"
            insert_btn.on_click = lambda i=row_index: self._insert_point_after(i)

            remove_btn = Button()
            remove_btn.text = "X"
            remove_btn.tooltip = "Remove point"
            remove_btn.on_click = lambda i=row_index: self._remove_point(i)

            row = (index_label, x_box, y_box, z_box, insert_btn, remove_btn)
            for widget in row:
                self.add_child(widget)
            self._point_rows.append(row)

        if self._ui is not None:
            self._ui.request_layout()

    def _set_point_component(self, row_index: int, component_index: int, value: float) -> None:
        if row_index < 0 or row_index >= len(self._value):
            log.error(f"[Vec3ListFieldWidget] row index out of range: {row_index}")
            return
        if component_index < 0 or component_index >= 3:
            log.error(f"[Vec3ListFieldWidget] component index out of range: {component_index}")
            return
        new_value = float(value)
        if self._value[row_index][component_index] == new_value:
            return
        self._value[row_index][component_index] = new_value
        self._emit()

    def _add_point(self) -> None:
        self._value.append([0.0, 0.0, 0.0])
        self._rebuild_rows()
        self._emit()

    def _insert_point_after(self, row_index: int) -> None:
        if row_index < 0 or row_index >= len(self._value):
            log.error(f"[Vec3ListFieldWidget] insert index out of range: {row_index}")
            return
        self._value.insert(row_index + 1, [0.0, 0.0, 0.0])
        self._rebuild_rows()
        self._emit()

    def _remove_point(self, row_index: int) -> None:
        if row_index < 0 or row_index >= len(self._value):
            log.error(f"[Vec3ListFieldWidget] remove index out of range: {row_index}")
            return
        del self._value[row_index]
        self._rebuild_rows()
        self._emit()

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        return (360.0, 24.0 + len(self._value) * 28.0 + 28.0)

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float) -> None:
        Widget.layout(self, x, y, width, height, viewport_w, viewport_h)
        header_h = 20.0
        row_h = 24.0
        gap = 4.0
        index_w = 34.0
        button_w = 24.0
        actions_w = button_w * 2.0 + gap
        coord_w = max(48.0, (width - index_w - actions_w - gap * 5.0) / 3.0)

        self._header.layout(x, y, width, header_h, viewport_w, viewport_h)

        row_y = y + header_h + gap
        for index_label, x_box, y_box, z_box, insert_btn, remove_btn in self._point_rows:
            cursor_x = x
            index_label.layout(cursor_x, row_y, index_w, row_h, viewport_w, viewport_h)
            cursor_x += index_w + gap
            x_box.layout(cursor_x, row_y, coord_w, row_h, viewport_w, viewport_h)
            cursor_x += coord_w + gap
            y_box.layout(cursor_x, row_y, coord_w, row_h, viewport_w, viewport_h)
            cursor_x += coord_w + gap
            z_box.layout(cursor_x, row_y, coord_w, row_h, viewport_w, viewport_h)
            cursor_x += coord_w + gap
            insert_btn.layout(cursor_x, row_y, button_w, row_h, viewport_w, viewport_h)
            cursor_x += button_w + gap
            remove_btn.layout(cursor_x, row_y, button_w, row_h, viewport_w, viewport_h)
            row_y += row_h + gap

        self._add_btn.layout(x, row_y, min(104.0, width), row_h, viewport_w, viewport_h)


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
# NavMeshArea
# ------------------------------------------------------------------

class NavMeshAreaFieldWidget(FieldWidget):
    """ComboBox with Detour area names from NavigationSettingsManager."""

    def __init__(self) -> None:
        super().__init__()
        self._selected_area_index = 0
        self._combo = ComboBox()
        self._combo.on_changed = self._on_changed
        self.add_child(self._combo)
        self._refresh_choices()

    def _refresh_choices(self) -> None:
        old = self._combo.on_changed
        self._combo.on_changed = None
        current = self._combo.selected_index
        self._combo.clear()
        try:
            from termin.navmesh.settings import NAVMESH_AREA_COUNT, NavigationSettingsManager
            manager = NavigationSettingsManager.instance()
            for area_index in range(NAVMESH_AREA_COUNT):
                self._combo.add_item(f"{area_index}: {manager.navmesh_area_label(area_index)}")
        except Exception as e:
            log.debug(f"[NavMeshAreaFieldWidget] Failed to get navmesh areas: {e}")
            for area_index in range(64):
                label = "Walkable" if area_index == 0 else f"Area {area_index}"
                self._combo.add_item(f"{area_index}: {label}")
        if 0 <= current < self._combo.item_count:
            self._combo.selected_index = current
        elif self._combo.item_count > 0:
            self._combo.selected_index = 0
        self._selected_area_index = max(0, self._combo.selected_index)
        self._combo.on_changed = old

    def _on_changed(self, index: int, _text: str) -> None:
        self._selected_area_index = max(0, index)
        self._emit()

    def get_value(self) -> int:
        return self._selected_area_index

    def set_value(self, value: Any) -> None:
        old = self._combo.on_changed
        self._combo.on_changed = None
        self._refresh_choices()
        try:
            area_index = int(value)
        except (TypeError, ValueError):
            area_index = 0
        if area_index < 0:
            area_index = 0
        if area_index >= self._combo.item_count:
            area_index = self._combo.item_count - 1
        self._combo.selected_index = area_index
        self._selected_area_index = max(0, area_index)
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
                from termin.inspect import InspectRegistry
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
        self._create_btn = Button()
        self._create_btn.text = "+"
        self._create_btn.on_click = self._on_create_clicked
        self.add_child(self._create_btn)
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
        self._create_btn.visible = accessors.create_item is not None

    def _on_changed(self, _index: int, _text: str) -> None:
        self._emit()

    def _on_create_clicked(self) -> None:
        accessors = self._get_accessors()
        if accessors is None or accessors.create_item is None:
            return
        created = accessors.create_item()
        if created is None:
            return
        created_name, _created_uuid = created
        self._refresh_items()
        for i in range(self._combo.item_count):
            if self._combo.item_text(i) == created_name:
                self._combo.selected_index = i
                break
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

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float) -> None:
        Widget.layout(self, x, y, width, height, viewport_w, viewport_h)
        button_w = 26.0 if self._create_btn.visible else 0.0
        gap = 4.0 if self._create_btn.visible else 0.0
        self._combo.layout(x, y, max(0.0, width - button_w - gap), height, viewport_w, viewport_h)
        if self._create_btn.visible:
            self._create_btn.layout(x + width - button_w, y, button_w, height, viewport_w, viewport_h)


class SerializedListFieldWidget(FieldWidget):
    """Scrollable inspector widget for serialized list fields."""

    def __init__(self, element_kind: str = "") -> None:
        super().__init__()
        self._element_kind = element_kind
        self._value: list[Any] = []
        self._label_prefix = "Items"

        self._count_label = Label()
        self._count_label.text = "0 items"
        self._list = ListWidget()
        self._list.item_height = 34
        self._list.empty_text = "Empty"
        self._list.preferred_height = px(112)

        self.add_child(self._count_label)
        self.add_child(self._list)

    def bind_field(self, key: str, field: "InspectField", target: Any) -> None:
        super().bind_field(key, field, target)
        self._label_prefix = field.label or key

    def full_row(self) -> bool:
        return True

    def get_value(self) -> list[Any]:
        return list(self._value)

    def set_value(self, value: Any) -> None:
        if value is None:
            self._value = []
        elif isinstance(value, list):
            self._value = list(value)
        else:
            self._value = [value]
        self._rebuild()

    def _item_title(self, index: int, item: Any) -> str:
        if isinstance(item, dict):
            name = item.get("name")
            uuid = item.get("uuid")
            if name:
                return f"{index}: {name}"
            if uuid:
                return f"{index}: {uuid}"
        return f"{index}: {item}"

    def _item_subtitle(self, item: Any) -> str:
        if isinstance(item, dict):
            uuid = item.get("uuid")
            item_type = item.get("type")
            if uuid and item_type:
                return f"{item_type}  {uuid}"
            if uuid:
                return str(uuid)
        return self._element_kind

    def _rebuild(self) -> None:
        count = len(self._value)
        label = "item" if count == 1 else "items"
        self._count_label.text = f"{self._label_prefix}: {count} {label}"
        items = []
        for i, item in enumerate(self._value):
            items.append({
                "text": self._item_title(i, item),
                "subtitle": self._item_subtitle(item),
                "data": item,
            })
        self._list.set_items(items)

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        list_h = min(156.0, max(42.0, len(self._value) * 36.0 + 4.0))
        return (320.0, 22.0 + list_h)

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float) -> None:
        Widget.layout(self, x, y, width, height, viewport_w, viewport_h)
        self._count_label.layout(x, y, width, 20.0, viewport_w, viewport_h)
        self._list.layout(x, y + 22.0, width, max(24.0, height - 22.0), viewport_w, viewport_h)


class EntityListFieldWidget(SerializedListFieldWidget):
    """Unity-like list widget for fields storing Entity UUID references."""

    def __init__(self, scene_getter: Callable[[], Any] | None = None) -> None:
        super().__init__("entity")
        self._scene_getter = scene_getter
        self._up_btn = Button()
        self._up_btn.text = "Up"
        self._up_btn.on_click = self._move_up
        self._down_btn = Button()
        self._down_btn.text = "Down"
        self._down_btn.on_click = self._move_down
        self._remove_btn = Button()
        self._remove_btn.text = "Remove"
        self._remove_btn.on_click = self._remove_selected
        self.add_child(self._up_btn)
        self.add_child(self._down_btn)
        self.add_child(self._remove_btn)

    def _entity_label(self, uuid: str) -> str:
        scene = self._scene_getter() if self._scene_getter is not None else None
        if scene is not None:
            entity = scene.get_entity(uuid)
            if entity is not None and entity.valid():
                return str(entity.name)
        return uuid

    def _item_title(self, index: int, item: Any) -> str:
        if isinstance(item, dict):
            uuid = item.get("uuid")
            if uuid:
                return f"{index}: {self._entity_label(str(uuid))}"
        return super()._item_title(index, item)

    def _item_subtitle(self, item: Any) -> str:
        if isinstance(item, dict):
            uuid = item.get("uuid")
            if uuid:
                return str(uuid)
        return ""

    def _move_up(self) -> None:
        idx = self._list.selected_index
        if idx <= 0 or idx >= len(self._value):
            return
        self._value[idx - 1], self._value[idx] = self._value[idx], self._value[idx - 1]
        self._list.selected_index = idx - 1
        self._rebuild()
        self._emit()

    def _move_down(self) -> None:
        idx = self._list.selected_index
        if idx < 0 or idx >= len(self._value) - 1:
            return
        self._value[idx + 1], self._value[idx] = self._value[idx], self._value[idx + 1]
        self._list.selected_index = idx + 1
        self._rebuild()
        self._emit()

    def _remove_selected(self) -> None:
        idx = self._list.selected_index
        if idx < 0 or idx >= len(self._value):
            return
        del self._value[idx]
        self._list.selected_index = min(idx, len(self._value) - 1)
        self._rebuild()
        self._emit()

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        list_h = min(156.0, max(42.0, len(self._value) * 36.0 + 4.0))
        return (320.0, 50.0 + list_h)

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float) -> None:
        Widget.layout(self, x, y, width, height, viewport_w, viewport_h)
        self._count_label.layout(x, y, width, 20.0, viewport_w, viewport_h)
        list_h = max(24.0, height - 50.0)
        self._list.layout(x, y + 22.0, width, list_h, viewport_w, viewport_h)
        btn_y = y + 24.0 + list_h
        btn_w = min(72.0, max(48.0, (width - 8.0) / 3.0))
        self._up_btn.layout(x, btn_y, btn_w, 24.0, viewport_w, viewport_h)
        self._down_btn.layout(x + btn_w + 4.0, btn_y, btn_w, 24.0, viewport_w, viewport_h)
        self._remove_btn.layout(x + (btn_w + 4.0) * 2.0, btn_y, btn_w, 24.0, viewport_w, viewport_h)


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

        if kind == "list[vec3]":
            return Vec3ListFieldWidget(
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

        if kind == "navmesh_area":
            return NavMeshAreaFieldWidget()

        if kind in ("entity_list", "list[entity]"):
            return EntityListFieldWidget(self._scene_getter)

        if kind.startswith("list[") and kind.endswith("]"):
            return SerializedListFieldWidget(kind[5:-1])

        if kind in (
            "tc_material", "mesh_handle", "tc_mesh",
            "skeleton_handle", "tc_skeleton",
            "voxel_grid_handle", "navmesh_handle",
            "tc_texture", "texture_handle", "ui_handle",
            "foliage_data_handle",
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
