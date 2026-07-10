"""MaterialInspector for tcgui."""

from __future__ import annotations

from typing import Optional, Callable, Any

from tcbase import log
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.grid_layout import GridLayout
from tcgui.widgets.label import Label
from tcgui.widgets.text_input import TextInput
from tcgui.widgets.combo_box import ComboBox
from tcgui.widgets.checkbox import Checkbox
from tcgui.widgets.spin_box import SpinBox
from tcgui.widgets.button import Button
from tcgui.widgets.color_dialog import ColorDialog
from tcgui.widgets.separator import Separator
from tcgui.widgets.units import px
from termin.editor_core.material_inspector_model import (
    MaterialInspectorController,
    MaterialPropertySnapshot,
    material_vector,
)
from termin.editor_tcgui.widgets.texture_picker import TexturePickerWidget, find_rt_texture


def _to_vec_list(value: Any, n: int, color_mode: bool = False) -> list[float]:
    """Compatibility helper backed by the shared material value contract."""
    return list(material_vector(value, n, color=color_mode))


class _VecEditor(HStack):
    """Compact N-component numeric editor."""

    def __init__(self, n: int, on_changed: Callable[[list[float]], None]) -> None:
        super().__init__()
        self.spacing = 2
        self._n = n
        self._on_changed = on_changed
        self._updating = False
        self._boxes: list[SpinBox] = []

        for _ in range(n):
            sb = SpinBox()
            sb.decimals = 4
            sb.step = 0.05
            sb.min_value = -1e6
            sb.max_value = 1e6
            sb.preferred_width = px(66)
            sb.on_changed = self._emit
            self.add_child(sb)
            self._boxes.append(sb)

    def _emit(self, _v: float) -> None:
        if self._updating:
            return
        self._on_changed([b.value for b in self._boxes])

    def set_value(self, value: Any, color_clamp: bool = False) -> None:
        self._updating = True
        try:
            vals = _to_vec_list(value, self._n, color_mode=color_clamp)
            for i, sb in enumerate(self._boxes):
                if color_clamp:
                    sb.min_value = 0.0
                    sb.max_value = 1.0
                sb.value = float(vals[i])
        finally:
            self._updating = False


class _ColorEditor(HStack):
    """RGBA editor: swatch button with ColorDialog."""

    def __init__(self, on_changed: Callable[[list[float]], None]) -> None:
        super().__init__()
        self.spacing = 2
        self._on_changed = on_changed
        self._updating = False
        self._pick_btn = Button()
        self._pick_btn.text = ""
        self._pick_btn.preferred_width = px(72)
        self._pick_btn.preferred_height = px(24)
        self._pick_btn.on_click = self._on_pick_clicked
        self.add_child(self._pick_btn)
        self._value = [1.0, 1.0, 1.0, 1.0]
        self._sync_button()
        self.preferred_height = px(24)

    def _sync_button(self) -> None:
        r, g, b, _a = self._value
        self._pick_btn.background_color = (r, g, b, 1.0)

    def _on_pick_clicked(self) -> None:
        if self._ui is None:
            return
        r, g, b, a = self._value
        initial = (
            int(max(0, min(255, round(r * 255.0)))),
            int(max(0, min(255, round(g * 255.0)))),
            int(max(0, min(255, round(b * 255.0)))),
            int(max(0, min(255, round(a * 255.0)))),
        )

        def _on_result(rgba: tuple[int, int, int, int] | None) -> None:
            if rgba is None:
                return
            self.set_value(
                [
                    rgba[0] / 255.0,
                    rgba[1] / 255.0,
                    rgba[2] / 255.0,
                    rgba[3] / 255.0,
                ]
            )
            self._on_changed(list(self._value))

        ColorDialog.pick_color(self._ui, initial=initial, show_alpha=True, on_result=_on_result)

    def set_value(self, value: Any) -> None:
        self._updating = True
        try:
            self._value = _to_vec_list(value, 4, color_mode=True)
            self._sync_button()
        finally:
            self._updating = False


class MaterialInspectorTcgui(VStack):
    """Inspector for TcMaterial with editable uniforms."""

    def __init__(self, resource_manager) -> None:
        super().__init__()
        self.spacing = 4
        self._rm = resource_manager
        self._controller = MaterialInspectorController(
            resource_manager,
            changed=self._on_controller_changed,
            render_target_texture=find_rt_texture,
        )
        self._material = None
        self._updating = False
        self.on_changed: Optional[Callable[[], None]] = None
        self._uniform_rows: dict[str, object] = {}
        self._scene_getter: Optional[Callable[[], list[Any]]] = None

        title = Label()
        title.text = "Material Inspector"
        self.add_child(title)

        self._subtitle = Label()
        self._subtitle.color = (0.62, 0.66, 0.74, 1.0)
        self.add_child(self._subtitle)
        self.add_child(Separator())

        grid = GridLayout(columns=2)
        grid.column_spacing = 4
        grid.row_spacing = 4
        grid.set_column_stretch(1, 1.0)
        self.add_child(grid)

        lbl_name = Label()
        lbl_name.text = "Name:"
        lbl_name.preferred_width = px(80)
        grid.add(lbl_name, 0, 0)
        self._name_input = TextInput()
        self._name_input.on_submit = self._on_name_submitted
        grid.add(self._name_input, 0, 1)

        lbl_uuid = Label()
        lbl_uuid.text = "UUID:"
        lbl_uuid.preferred_width = px(80)
        grid.add(lbl_uuid, 1, 0)
        self._uuid_label = Label()
        self._uuid_label.color = (0.55, 0.60, 0.68, 1.0)
        grid.add(self._uuid_label, 1, 1)

        lbl_shader = Label()
        lbl_shader.text = "Shader:"
        lbl_shader.preferred_width = px(80)
        grid.add(lbl_shader, 2, 0)
        self._shader_combo = ComboBox()
        self._shader_combo.on_changed = self._on_shader_changed
        grid.add(self._shader_combo, 2, 1)

        self._phases_info = Label()
        grid.add(self._phases_info, 3, 1)

        self.add_child(Separator())

        self._uniform_grid = GridLayout(columns=2)
        self._uniform_grid.column_spacing = 4
        self._uniform_grid.row_spacing = 4
        self._uniform_grid.set_column_stretch(1, 1.0)
        self.add_child(self._uniform_grid)

        self._empty_label = Label()
        self._empty_label.text = "Material not found."
        self._empty_label.color = (0.52, 0.56, 0.62, 1.0)
        self.add_child(self._empty_label)

        self._set_visible_state(False)

    def set_scene_getter(self, getter: Callable[[], list[Any]]) -> None:
        self._scene_getter = getter

    def set_target(self, material, subtitle: str = "") -> None:
        self._material = material
        self._controller.set_target(material)
        self._subtitle.text = subtitle
        self._refresh()

    def _set_visible_state(self, has_material: bool) -> None:
        self._name_input.visible = has_material
        self._uuid_label.visible = has_material
        self._shader_combo.visible = has_material
        self._phases_info.visible = has_material
        self._uniform_grid.visible = has_material
        self._empty_label.visible = not has_material

    def _refresh(self) -> None:
        self._updating = True
        try:
            snapshot = self._controller.refresh()
            mat = self._material
            self._uniform_grid.clear()
            self._uniform_rows.clear()
            if mat is None:
                self._set_visible_state(False)
                return

            self._set_visible_state(True)
            self._name_input.text = snapshot.name
            self._uuid_label.text = snapshot.uuid or "—"

            self._shader_combo.clear()
            shader_names = snapshot.shader_choices
            selected_idx = -1
            for i, shader_name in enumerate(shader_names):
                self._shader_combo.add_item(shader_name)
                if shader_name == snapshot.shader_name:
                    selected_idx = i
            self._shader_combo.selected_index = selected_idx

            self._phases_info.text = f"Phases: {snapshot.phase_count}"
            self._build_uniform_rows(snapshot.properties, snapshot.message)
        finally:
            self._updating = False
            if self._ui is not None:
                self._ui.request_layout()

    def _build_uniform_rows(
        self,
        properties: tuple[MaterialPropertySnapshot, ...],
        message: str,
    ) -> None:
        if message:
            msg = Label()
            msg.text = message
            msg.color = (0.7, 0.55, 0.4, 1.0)
            self._uniform_grid.add(msg, 0, 0, 1, 2)
            return

        row = 0
        for prop in properties:
            name = prop.name
            label = Label()
            label.text = (prop.label or name) + ":"
            label.preferred_width = px(120)
            self._uniform_grid.add(label, row, 0)

            editor = self._create_editor(prop)
            self._uniform_grid.add(editor, row, 1)
            row += 1

    def _set_uniform_all_phases(self, uniform_name: str, value: Any) -> None:
        self._controller.set_property(uniform_name, value)

    def _set_texture_all_phases(
        self,
        uniform_name: str,
        tag: str,
        texture_name: str,
        default_tex: str = "white",
    ) -> None:
        self._controller.set_texture(
            uniform_name,
            tag,
            texture_name,
            default_kind=default_tex,
        )

    def _create_editor(self, prop: MaterialPropertySnapshot) -> object:
        ptype = prop.kind
        name = prop.name
        current = prop.value

        if ptype == "Bool":
            cb = Checkbox()
            cb.checked = bool(current)
            cb.on_changed = lambda checked, n=name: self._set_uniform_all_phases(n, bool(checked))
            return cb

        if ptype == "Float":
            sb = SpinBox()
            sb.decimals = 3
            sb.step = 0.1
            sb.min_value = prop.minimum if prop.minimum is not None else -1e6
            sb.max_value = prop.maximum if prop.maximum is not None else 1e6
            sb.value = float(current) if current is not None else 0.0
            sb.on_changed = lambda v, n=name: self._set_uniform_all_phases(n, float(v))
            return sb

        if ptype == "Int":
            sb = SpinBox()
            sb.decimals = 0
            sb.step = 1.0
            sb.min_value = prop.minimum if prop.minimum is not None else -1e6
            sb.max_value = prop.maximum if prop.maximum is not None else 1e6
            sb.value = int(current) if current is not None else 0
            sb.on_changed = lambda v, n=name: self._set_uniform_all_phases(n, int(v))
            return sb

        if ptype == "Color":
            editor = _ColorEditor(lambda arr, nname=name: self._on_vec_changed(nname, "Color", arr))
            editor.set_value(current)
            return editor

        if ptype in ("Vec2", "Vec3", "Vec4"):
            n = 2 if ptype == "Vec2" else (3 if ptype == "Vec3" else 4)
            editor = _VecEditor(n, lambda arr, nname=name, kind=ptype: self._on_vec_changed(nname, kind, arr))
            editor.set_value(current, color_clamp=False)
            return editor

        if ptype in ("Texture", "Texture2D"):
            texture = prop.texture
            selected_name = "" if texture is None else texture.name
            selected_tag = "default" if texture is None else texture.tag
            default_tex = "white" if texture is None else texture.default_kind

            editor = TexturePickerWidget(
                self._rm,
                on_changed=lambda tag, val, n=name, d=default_tex: self._set_texture_all_phases(n, tag, val, d),
                scene_getter=self._scene_getter,
                default_texture_kind=default_tex,
            )
            editor.set_value(selected_name, selected_tag)
            log.info(
                f"[MaterialInspectorTcgui] texture picker value set: "
                f"material='{self._material.name if self._material is not None else '<none>'}' "
                f"uniform='{name}' selected_tag='{selected_tag}' selected_name='{selected_name}' "
                f"default='{default_tex}'"
            )
            return editor

        unknown = Label()
        unknown.text = str(current)
        unknown.color = (0.72, 0.64, 0.46, 1.0)
        return unknown

    def _on_vec_changed(self, uniform_name: str, ptype: str, arr: list[float]) -> None:
        self._controller.set_property(uniform_name, arr)

    def _on_name_submitted(self, text: str) -> None:
        if self._updating or self._material is None:
            return
        new_name = text.strip()
        if not new_name:
            return
        if self._material.name != new_name:
            self._controller.set_name(new_name)
            self._refresh()

    def _on_shader_changed(self, index: int, shader_name: str) -> None:
        if self._updating or self._material is None:
            return
        if index < 0 or not shader_name:
            return
        if shader_name == self._material.shader_name:
            return
        try:
            self._controller.set_shader(shader_name)
            self._refresh()
        except Exception as e:
            log.error(f"[MaterialInspectorTcgui] Failed to apply shader '{shader_name}': {e}")

    def _on_controller_changed(self) -> None:
        if self.on_changed is not None:
            self.on_changed()
