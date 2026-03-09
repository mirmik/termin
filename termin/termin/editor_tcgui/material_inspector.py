"""MaterialInspector for tcgui."""

from __future__ import annotations

from typing import Optional, Callable, Any
import numpy as np

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
from tcgui.widgets.widget import Widget
from tcgui.widgets.separator import Separator
from tcgui.widgets.units import px


def _to_vec_list(value: Any, n: int, color_mode: bool = False) -> list[float]:
    """Convert various vector-like values to a list of N floats."""
    vals: list[float] = []

    if isinstance(value, (list, tuple)):
        vals = [float(v) for v in value[:n]]
    else:
        try:
            vals = [float(v) for v in value]
            vals = vals[:n]
        except Exception:
            vals = []

        # Native Vec3/Vec4 path (nanobind object with x/y/z/w fields)
        if not vals:
            try:
                vals = [float(value.x), float(value.y), float(value.z)]
                if n >= 4:
                    try:
                        vals.append(float(value.w))
                    except Exception:
                        vals.append(1.0 if color_mode else 0.0)
            except Exception:
                vals = []

    if len(vals) < n:
        fill = 1.0 if color_mode and n == 4 and len(vals) == 3 else 0.0
        vals.extend([fill] * (n - len(vals)))

    if color_mode:
        vals = [max(0.0, min(1.0, v)) for v in vals]

    return vals[:n]


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


class _TexturePreview(Widget):
    """Small texture preview widget (48x48) with placeholder."""

    def __init__(self) -> None:
        super().__init__()
        self.preferred_width = px(48)
        self.preferred_height = px(48)
        self._image_data: np.ndarray | None = None
        self._gpu_texture = None
        self._dirty = False
        self._placeholder = "No\nTex"

    def set_image(self, data: Any, placeholder: str = "No\nTex") -> None:
        self._placeholder = placeholder
        self._image_data = None
        self._dirty = True

        if data is None:
            return

        try:
            arr = np.asarray(data)
            if arr.ndim != 3:
                return
            if arr.shape[2] == 4:
                self._image_data = np.ascontiguousarray(arr.astype(np.uint8))
            elif arr.shape[2] == 3:
                alpha = np.full((arr.shape[0], arr.shape[1], 1), 255, dtype=np.uint8)
                rgb = arr.astype(np.uint8)
                self._image_data = np.ascontiguousarray(np.concatenate([rgb, alpha], axis=2))
        except Exception:
            self._image_data = None

    def _sync_texture(self, renderer) -> None:
        if not self._dirty:
            return
        self._dirty = False

        if self._gpu_texture is not None:
            try:
                self._gpu_texture.delete()
            except Exception:
                pass
            self._gpu_texture = None

        if self._image_data is not None:
            try:
                self._gpu_texture = renderer.upload_texture(self._image_data)
            except Exception as e:
                log.error(f"[MaterialInspectorTcgui] failed to upload texture preview: {e}")
                self._gpu_texture = None

    def render(self, renderer) -> None:
        self._sync_texture(renderer)

        renderer.draw_rect(self.x, self.y, self.width, self.height, (0.17, 0.18, 0.22, 1.0))
        renderer.draw_rect_outline(self.x, self.y, self.width, self.height, (0.36, 0.38, 0.44, 1.0), 1.0)

        if self._gpu_texture is not None:
            renderer.draw_image(self.x + 1, self.y + 1, self.width - 2, self.height - 2, self._gpu_texture)
        else:
            renderer.draw_text_centered(
                self.x + self.width * 0.5,
                self.y + self.height * 0.5,
                self._placeholder,
                (0.56, 0.58, 0.64, 1.0),
                10.0,
            )


class _TextureEditor(HStack):
    """Texture selector with preview and combo box."""

    def __init__(
        self,
        resource_manager,
        on_changed: Callable[[str], None],
        default_texture_kind: str = "white",
    ) -> None:
        super().__init__()
        self.spacing = 8
        self._rm = resource_manager
        self._on_changed = on_changed
        self._default_texture_kind = default_texture_kind
        self._updating = False

        self._preview = _TexturePreview()
        self.add_child(self._preview)

        self._combo = ComboBox()
        self._combo.stretch = True
        self._combo.on_changed = self._on_combo_changed
        self.add_child(self._combo)

    def set_value(self, selected_name: str | None) -> None:
        self._updating = True
        try:
            self._combo.clear()
            self._combo.add_item("(default)")
            for tname in self._rm.list_texture_names():
                if tname == "__white_1x1__":
                    continue
                self._combo.add_item(tname)

            selected = selected_name or "(default)"
            if selected != "(default)":
                exists = False
                for i in range(self._combo.item_count):
                    if self._combo.item_text(i) == selected:
                        exists = True
                        break
                if not exists:
                    self._combo.add_item(selected)

            self._set_combo_selected(selected)
            self._update_preview(selected)
        finally:
            self._updating = False

    def _set_combo_selected(self, text: str) -> None:
        for i in range(self._combo.item_count):
            if self._combo.item_text(i) == text:
                self._combo.selected_index = i
                return
        self._combo.selected_index = 0

    def _resolve_preview_image(self, selected_text: str):
        if selected_text == "(default)":
            from termin.visualization.render.texture import get_white_texture, get_normal_texture

            tex = get_normal_texture() if self._default_texture_kind == "normal" else get_white_texture()
            return tex._image_data, "default"

        tex = self._rm.get_texture(selected_text)
        if tex is None:
            return None, "No\nTex"
        return tex._image_data, "No\nTex"

    def _update_preview(self, selected_text: str) -> None:
        img, placeholder = self._resolve_preview_image(selected_text)
        self._preview.set_image(img, placeholder=placeholder)

    def _on_combo_changed(self, _index: int, text: str) -> None:
        self._update_preview(text)
        if self._updating:
            return
        self._on_changed("" if text == "(default)" else text)


class MaterialInspectorTcgui(VStack):
    """Inspector for TcMaterial with editable uniforms."""

    def __init__(self, resource_manager) -> None:
        super().__init__()
        self.spacing = 4
        self._rm = resource_manager
        self._material = None
        self._updating = False
        self.on_changed: Optional[Callable[[], None]] = None
        self._uniform_rows: dict[str, object] = {}

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

    def set_target(self, material, subtitle: str = "") -> None:
        self._material = material
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
            mat = self._material
            self._uniform_grid.clear()
            self._uniform_rows.clear()
            if mat is None:
                self._set_visible_state(False)
                return

            self._set_visible_state(True)
            self._name_input.text = mat.name or ""
            self._uuid_label.text = mat.uuid if mat.uuid else "—"

            self._shader_combo.clear()
            shader_names = self._rm.list_shader_names()
            selected_idx = -1
            for i, shader_name in enumerate(shader_names):
                self._shader_combo.add_item(shader_name)
                if shader_name == mat.shader_name:
                    selected_idx = i
            self._shader_combo.selected_index = selected_idx

            phase_count = len(mat.phases) if mat.phases else 0
            self._phases_info.text = f"Phases: {phase_count}"
            self._build_uniform_rows()
        finally:
            self._updating = False
            if self._ui is not None:
                self._ui.request_layout()

    def _build_uniform_rows(self) -> None:
        if self._material is None:
            return
        program = self._rm.get_shader(self._material.shader_name)
        if program is None or not program.phases:
            msg = Label()
            msg.text = "Shader metadata unavailable."
            msg.color = (0.7, 0.55, 0.4, 1.0)
            self._uniform_grid.add(msg, 0, 0, 1, 2)
            return

        row = 0
        props: dict[str, Any] = {}
        for phase in program.phases:
            for prop in phase.uniforms:
                if prop.name not in props:
                    props[prop.name] = prop

        for name, prop in props.items():
            label = Label()
            label.text = (prop.label or name) + ":"
            label.preferred_width = px(120)
            self._uniform_grid.add(label, row, 0)

            editor = self._create_editor(prop)
            self._uniform_grid.add(editor, row, 1)
            row += 1

    def _get_uniform_value(self, uniform_name: str, default: Any) -> Any:
        if self._material is None or not self._material.phases:
            return default
        first = self._material.phases[0]
        if uniform_name in first.uniforms:
            return first.uniforms[uniform_name]
        return default

    def _set_uniform_all_phases(self, uniform_name: str, value: Any) -> None:
        if self._material is None:
            return
        for phase in self._material.phases:
            phase.set_param(uniform_name, value)
        self._emit_changed()

    def _set_texture_all_phases(self, uniform_name: str, texture_name: str, default_tex: str = "white") -> None:
        if self._material is None:
            return
        from termin.visualization.core.texture_handle import (
            get_white_texture_handle,
            get_normal_texture_handle,
        )

        if texture_name:
            handle = self._rm.get_texture_handle(texture_name)
        else:
            handle = get_normal_texture_handle() if default_tex == "normal" else get_white_texture_handle()

        if handle is None:
            log.error(f"[MaterialInspectorTcgui] texture handle not found: {texture_name}")
            return

        for phase in self._material.phases:
            phase.set_texture(uniform_name, handle)
        self._emit_changed()

    def _create_editor(self, prop) -> object:
        ptype = prop.property_type
        name = prop.name
        default = prop.default
        current = self._get_uniform_value(name, default)

        if ptype == "Bool":
            cb = Checkbox()
            cb.checked = bool(current)
            cb.on_changed = lambda checked, n=name: self._set_uniform_all_phases(n, bool(checked))
            return cb

        if ptype == "Float":
            sb = SpinBox()
            sb.decimals = 3
            sb.step = 0.1
            sb.min_value = float(prop.range_min) if prop.range_min is not None else -1e6
            sb.max_value = float(prop.range_max) if prop.range_max is not None else 1e6
            sb.value = float(current) if current is not None else 0.0
            sb.on_changed = lambda v, n=name: self._set_uniform_all_phases(n, float(v))
            return sb

        if ptype == "Int":
            sb = SpinBox()
            sb.decimals = 0
            sb.step = 1.0
            sb.min_value = float(prop.range_min) if prop.range_min is not None else -1e6
            sb.max_value = float(prop.range_max) if prop.range_max is not None else 1e6
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
            selected = "(default)"
            if self._material is not None and self._material.phases:
                tex = self._material.phases[0].textures.get(name)
                if tex is not None:
                    tname = self._rm.find_texture_name(tex)
                    if tname:
                        selected = tname

            default_tex = "white"
            if isinstance(default, str) and default in ("white", "normal"):
                default_tex = default

            editor = _TextureEditor(
                self._rm,
                on_changed=lambda tex_name, n=name, d=default_tex: self._set_texture_all_phases(n, tex_name, d),
                default_texture_kind=default_tex,
            )
            editor.set_value(None if selected == "(default)" else selected)
            return editor

        unknown = Label()
        unknown.text = str(current)
        unknown.color = (0.72, 0.64, 0.46, 1.0)
        return unknown

    def _on_vec_changed(self, uniform_name: str, ptype: str, arr: list[float]) -> None:
        from termin.geombase import Vec3, Vec4
        if ptype == "Vec2":
            self._set_uniform_all_phases(uniform_name, [float(arr[0]), float(arr[1])])
            return
        if ptype == "Vec3":
            self._set_uniform_all_phases(uniform_name, Vec3(float(arr[0]), float(arr[1]), float(arr[2])))
            return
        self._set_uniform_all_phases(
            uniform_name,
            Vec4(float(arr[0]), float(arr[1]), float(arr[2]), float(arr[3])),
        )

    def _on_name_submitted(self, text: str) -> None:
        if self._updating or self._material is None:
            return
        new_name = text.strip()
        if not new_name:
            return
        if self._material.name != new_name:
            self._material.name = new_name
            self._emit_changed()
            self._refresh()

    def _on_shader_changed(self, index: int, shader_name: str) -> None:
        if self._updating or self._material is None:
            return
        if index < 0 or not shader_name:
            return
        if shader_name == self._material.shader_name:
            return
        try:
            from termin.assets.shader_asset import update_material_shader
            program = self._rm.get_shader(shader_name)
            if program is None:
                log.error(f"[MaterialInspectorTcgui] Shader not found: {shader_name}")
                return
            shader_asset = self._rm.get_shader_asset(shader_name)
            shader_uuid = shader_asset.uuid if shader_asset is not None else ""
            update_material_shader(self._material, program, shader_name, shader_uuid)
            self._emit_changed()
            self._refresh()
        except Exception as e:
            log.error(f"[MaterialInspectorTcgui] Failed to apply shader '{shader_name}': {e}")

    def _emit_changed(self) -> None:
        if self.on_changed is not None:
            self.on_changed()
