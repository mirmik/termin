"""Render target inspector for tcgui."""

from __future__ import annotations

from typing import Callable, Optional

from tcbase import log
from tcgui.widgets.vstack import VStack
from tcgui.widgets.grid_layout import GridLayout
from tcgui.widgets.label import Label
from tcgui.widgets.combo_box import ComboBox
from tcgui.widgets.checkbox import Checkbox
from tcgui.widgets.spin_box import SpinBox
from tcgui.widgets.separator import Separator
from tcgui.widgets.units import px

from termin.editor_tcgui.widgets.layer_mask_widget import LayerMaskFieldWidget
from termin.editor_tcgui.widgets.texture_picker import TexturePickerWidget


_COLOR_FORMATS = [
    ("rgba16f", "RGBA16F"),
    ("rgba8", "RGBA8"),
    ("rgb8", "RGB8"),
    ("rg8", "RG8"),
    ("r8", "R8"),
    ("r16f", "R16F"),
    ("r32f", "R32F"),
    ("rgb16f", "RGB16F"),
]

_DEPTH_FORMATS = [
    ("depth32f", "Depth 32F"),
    ("depth24", "Depth 24"),
]

_TARGET_KINDS = [
    ("texture_2d", "Texture 2D"),
    ("xr_stereo", "XR Stereo"),
]


class RenderTargetInspectorTcgui(VStack):
    """Inspector panel for RenderTarget properties."""

    def __init__(self, resource_manager) -> None:
        super().__init__()
        self.spacing = 4

        self._rm = resource_manager
        self._render_target = None
        self._scene = None
        self._scenes = []
        self._cameras = []
        self._target_kind_values = [value for value, _label in _TARGET_KINDS]
        self._color_format_values = [value for value, _label in _COLOR_FORMATS]
        self._depth_format_values = [value for value, _label in _DEPTH_FORMATS]
        self._updating = False
        self.on_changed: Optional[Callable[[], None]] = None
        self._scene_getter: Optional[Callable[[], list]] = None

        title = Label()
        title.text = "Render Target Inspector"
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

        enabled_lbl = Label(); enabled_lbl.text = "Enabled:"; enabled_lbl.preferred_width = px(96)
        self._enabled_lbl = enabled_lbl
        self._enabled = Checkbox()
        self._enabled.on_changed = self._on_enabled_changed
        grid.add(enabled_lbl, 0, 0)
        grid.add(self._enabled, 0, 1)

        scene_lbl = Label(); scene_lbl.text = "Scene:"; scene_lbl.preferred_width = px(96)
        self._scene_lbl = scene_lbl
        self._scene_combo = ComboBox()
        self._scene_combo.on_changed = self._on_scene_changed
        grid.add(scene_lbl, 1, 0)
        grid.add(self._scene_combo, 1, 1)

        cam_lbl = Label(); cam_lbl.text = "Camera:"; cam_lbl.preferred_width = px(96)
        self._camera_lbl = cam_lbl
        self._camera_combo = ComboBox()
        self._camera_combo.on_changed = self._on_camera_changed
        grid.add(cam_lbl, 2, 0)
        grid.add(self._camera_combo, 2, 1)

        pipe_lbl = Label(); pipe_lbl.text = "Pipeline:"; pipe_lbl.preferred_width = px(96)
        self._pipeline_lbl = pipe_lbl
        self._pipeline_combo = ComboBox()
        self._pipeline_combo.on_changed = self._on_pipeline_changed
        grid.add(pipe_lbl, 3, 0)
        grid.add(self._pipeline_combo, 3, 1)

        dynamic_lbl = Label(); dynamic_lbl.text = "Use View Size:"; dynamic_lbl.preferred_width = px(96)
        self._dynamic_lbl = dynamic_lbl
        self._dynamic_resolution = Checkbox()
        self._dynamic_resolution.on_changed = self._on_dynamic_resolution_changed
        grid.add(self._dynamic_lbl, 4, 0)
        grid.add(self._dynamic_resolution, 4, 1)

        color_format_lbl = Label(); color_format_lbl.text = "Color Format:"; color_format_lbl.preferred_width = px(96)
        self._color_format_lbl = color_format_lbl
        self._color_format = ComboBox()
        self._color_format.items = [label for _value, label in _COLOR_FORMATS]
        self._color_format.on_changed = self._on_color_format_changed
        grid.add(self._color_format_lbl, 5, 0)
        grid.add(self._color_format, 5, 1)

        depth_format_lbl = Label(); depth_format_lbl.text = "Depth Format:"; depth_format_lbl.preferred_width = px(96)
        self._depth_format_lbl = depth_format_lbl
        self._depth_format = ComboBox()
        self._depth_format.items = [label for _value, label in _DEPTH_FORMATS]
        self._depth_format.on_changed = self._on_depth_format_changed
        grid.add(self._depth_format_lbl, 6, 0)
        grid.add(self._depth_format, 6, 1)

        clear_color_lbl = Label(); clear_color_lbl.text = "Clear Color:"; clear_color_lbl.preferred_width = px(96)
        self._clear_color_lbl = clear_color_lbl
        self._clear_color = Checkbox()
        self._clear_color.on_changed = self._on_clear_color_changed
        grid.add(self._clear_color_lbl, 7, 0)
        grid.add(self._clear_color, 7, 1)

        self._clear_color_value_lbls: list[Label] = []
        self._clear_color_spins: list[SpinBox] = []
        for idx, label in enumerate(("R:", "G:", "B:", "A:"), start=8):
            lbl = Label(); lbl.text = label; lbl.preferred_width = px(96)
            spin = SpinBox()
            spin.decimals = 3
            spin.step = 0.05
            spin.min_value = -1000000.0
            spin.max_value = 1000000.0
            spin.on_changed = self._on_clear_color_value_changed
            self._clear_color_value_lbls.append(lbl)
            self._clear_color_spins.append(spin)
            grid.add(lbl, idx, 0)
            grid.add(spin, idx, 1)

        clear_depth_lbl = Label(); clear_depth_lbl.text = "Clear Depth:"; clear_depth_lbl.preferred_width = px(96)
        self._clear_depth_lbl = clear_depth_lbl
        self._clear_depth = Checkbox()
        self._clear_depth.on_changed = self._on_clear_depth_changed
        grid.add(self._clear_depth_lbl, 12, 0)
        grid.add(self._clear_depth, 12, 1)

        clear_depth_value_lbl = Label(); clear_depth_value_lbl.text = "Depth Value:"; clear_depth_value_lbl.preferred_width = px(96)
        self._clear_depth_value_lbl = clear_depth_value_lbl
        self._clear_depth_value = SpinBox()
        self._clear_depth_value.decimals = 4
        self._clear_depth_value.step = 0.01
        self._clear_depth_value.min_value = 0.0
        self._clear_depth_value.max_value = 1.0
        self._clear_depth_value.value = 1.0
        self._clear_depth_value.on_changed = self._on_clear_depth_value_changed
        grid.add(self._clear_depth_value_lbl, 13, 0)
        grid.add(self._clear_depth_value, 13, 1)

        width_lbl = Label(); width_lbl.text = "Width:"; width_lbl.preferred_width = px(96)
        self._width_lbl = width_lbl
        self._width = SpinBox()
        self._width.decimals = 0
        self._width.step = 64
        self._width.min_value = 1
        self._width.max_value = 8192
        self._width.value = 512
        self._width.on_changed = self._on_size_changed
        grid.add(self._width_lbl, 14, 0)
        grid.add(self._width, 14, 1)

        height_lbl = Label(); height_lbl.text = "Height:"; height_lbl.preferred_width = px(96)
        self._height_lbl = height_lbl
        self._height = SpinBox()
        self._height.decimals = 0
        self._height.step = 64
        self._height.min_value = 1
        self._height.max_value = 8192
        self._height.value = 512
        self._height.on_changed = self._on_size_changed
        grid.add(self._height_lbl, 15, 0)
        grid.add(self._height, 15, 1)

        kind_lbl = Label(); kind_lbl.text = "Type:"; kind_lbl.preferred_width = px(96)
        self._kind_lbl = kind_lbl
        self._kind_combo = ComboBox()
        self._kind_combo.items = [label for _value, label in _TARGET_KINDS]
        self._kind_combo.on_changed = self._on_kind_changed
        grid.add(self._kind_lbl, 16, 0)
        grid.add(self._kind_combo, 16, 1)

        mask_lbl = Label(); mask_lbl.text = "Layer Mask:"; mask_lbl.preferred_width = px(96)
        self._mask_lbl = mask_lbl
        self._layer_mask_widget = LayerMaskFieldWidget()
        self._layer_mask_widget.on_value_changed = self._on_layer_mask_changed
        grid.add(self._mask_lbl, 17, 0)
        grid.add(self._layer_mask_widget, 17, 1)

        self._pipeline_params_sep = Separator()
        self._pipeline_params_sep.visible = False
        self.add_child(self._pipeline_params_sep)

        self._pipeline_params_title = Label()
        self._pipeline_params_title.text = "Pipeline Parameters"
        self._pipeline_params_title.visible = False
        self.add_child(self._pipeline_params_title)

        self._pipeline_params_grid = GridLayout(columns=2)
        self._pipeline_params_grid.column_spacing = 4
        self._pipeline_params_grid.row_spacing = 4
        self._pipeline_params_grid.set_column_stretch(1, 1.0)
        self._pipeline_params_grid.visible = False
        self.add_child(self._pipeline_params_grid)

        self._pipeline_params_widgets: list[TexturePickerWidget] = []
        self._pipeline_params_slots: list[str] = []

        self._empty = Label()
        self._empty.text = "No render target selected."
        self._empty.color = (0.52, 0.56, 0.62, 1.0)
        self.add_child(self._empty)

        self._set_visible_state(False)

    def set_scene_getter(self, getter: Callable[[], list]) -> None:
        self._scene_getter = getter

    def set_scene(self, scene) -> None:
        self._scene = scene
        self._layer_mask_widget.set_scene_getter(lambda: self._scene)
        self._refresh_camera_combo()

    def set_render_target(self, render_target=None, scene=None) -> None:
        self._render_target = render_target
        if render_target is not None and render_target.scene is not None:
            self._scene = render_target.scene
        elif scene is not None:
            self._scene = scene

        self._updating = True
        try:
            if render_target is None:
                self._set_visible_state(False)
                return

            self._set_visible_state(True)
            rt_name = render_target.name or "<unnamed>"
            kind_label = self._target_kind_label(render_target.kind)
            self._subtitle.text = f"Render Target: {rt_name} [{kind_label}]"

            self._enabled.checked = bool(render_target.enabled)
            self._select_combo_value(self._kind_combo, self._target_kind_values, render_target.kind)

            self._refresh_scene_combo()
            self._select_current_scene()
            self._refresh_camera_combo()
            self._select_current_camera()
            self._refresh_pipeline_combo()
            self._select_current_pipeline()

            self._dynamic_resolution.checked = bool(render_target.dynamic_resolution)
            self._select_combo_value(self._color_format, self._color_format_values, render_target.color_format)
            self._select_combo_value(self._depth_format, self._depth_format_values, render_target.depth_format)
            self._clear_color.checked = bool(render_target.clear_color_enabled)
            for spin, value in zip(self._clear_color_spins, render_target.clear_color_value, strict=True):
                spin.value = float(value)
            self._clear_depth.checked = bool(render_target.clear_depth_enabled)
            self._clear_depth_value.value = float(render_target.clear_depth_value)
            self._width.value = render_target.width
            self._height.value = render_target.height
            self._layer_mask_widget.set_value(render_target.layer_mask)
            self._refresh_pipeline_params()
            self._update_kind_visibility()
        finally:
            self._updating = False
            if self._ui is not None:
                self._ui.request_layout()

    def _set_visible_state(self, has_target: bool) -> None:
        self._enabled_lbl.visible = has_target
        self._enabled.visible = has_target
        self._scene_lbl.visible = has_target
        self._scene_combo.visible = has_target
        self._camera_lbl.visible = has_target
        self._camera_combo.visible = has_target
        self._pipeline_lbl.visible = has_target
        self._pipeline_combo.visible = has_target
        self._kind_lbl.visible = has_target
        self._kind_combo.visible = has_target
        self._dynamic_lbl.visible = has_target
        self._dynamic_resolution.visible = has_target
        self._color_format_lbl.visible = has_target
        self._color_format.visible = has_target
        self._depth_format_lbl.visible = has_target
        self._depth_format.visible = has_target
        self._clear_color_lbl.visible = has_target
        self._clear_color.visible = has_target
        for lbl in self._clear_color_value_lbls:
            lbl.visible = has_target
        for spin in self._clear_color_spins:
            spin.visible = has_target
        self._clear_depth_lbl.visible = has_target
        self._clear_depth.visible = has_target
        self._clear_depth_value_lbl.visible = has_target
        self._clear_depth_value.visible = has_target
        self._mask_lbl.visible = has_target
        self._layer_mask_widget.visible = has_target
        self._update_size_visibility()
        self._empty.visible = not has_target
        self._update_kind_visibility()

    def _refresh_scene_combo(self) -> None:
        old = self._scene_combo.on_changed
        self._scene_combo.on_changed = None
        self._scene_combo.clear()
        self._scenes.clear()

        self._scene_combo.add_item("(none)")
        if self._scene_getter is not None:
            try:
                for scene in self._scene_getter():
                    name = scene.name or scene.uuid or "Scene"
                    self._scenes.append(scene)
                    self._scene_combo.add_item(name)
            except Exception as e:
                log.error(f"[RenderTargetInspector] scene scan failed: {e}")

        self._scene_combo.on_changed = old

    def _select_current_scene(self) -> None:
        if self._render_target is None or self._render_target.scene is None:
            self._scene_combo.selected_index = 0
            return
        rt_scene = self._render_target.scene
        for i, scene in enumerate(self._scenes):
            if scene.scene_handle().index == rt_scene.scene_handle().index:
                self._scene_combo.selected_index = i + 1
                return
        self._scene_combo.selected_index = 0

    def _on_scene_changed(self, index: int, _text: str) -> None:
        if self._updating or self._render_target is None:
            return
        if index <= 0:
            self._render_target.scene = None
            self._scene = None
            self._refresh_camera_combo()
            self._emit_changed()
            return
        if index < len(self._scenes) + 1:
            self._render_target.scene = self._scenes[index - 1]
            self._scene = self._scenes[index - 1]
            self._refresh_camera_combo()
            self._emit_changed()

    def _refresh_camera_combo(self) -> None:
        old = self._camera_combo.on_changed
        self._camera_combo.on_changed = None
        self._camera_combo.clear()
        self._cameras.clear()

        self._camera_combo.add_item("(none)")
        scene = self._camera_source_scene()
        if scene is not None:
            try:
                entities = scene.entities
                if not entities:
                    self._camera_combo.on_changed = old
                    return
                if self._is_xr_target():
                    from termin.render_components import XrOriginComponent
                    for ent in entities:
                        origin = ent.get_component(XrOriginComponent)
                        if origin is None:
                            continue
                        label = ent.name or ent.uuid or "XR Origin"
                        self._cameras.append(origin)
                        self._camera_combo.add_item(label)
                else:
                    from termin.render_components.camera import CameraComponent
                    for ent in entities:
                        cam = ent.get_component(CameraComponent)
                        if cam is None:
                            continue
                        label = ent.name or ent.uuid or "Camera"
                        self._cameras.append(cam)
                        self._camera_combo.add_item(label)
            except Exception as e:
                log.error(f"[RenderTargetInspector] render source scan failed: {e}")

        self._camera_combo.on_changed = old

    def _camera_source_scene(self):
        if self._render_target is not None and self._render_target.scene is not None:
            return self._render_target.scene
        return self._scene

    def _select_current_camera(self) -> None:
        if self._render_target is None:
            self._camera_combo.selected_index = 0
            return
        current = self._render_target.xr_origin if self._is_xr_target() else self._render_target.camera
        if current is None:
            self._camera_combo.selected_index = 0
            return
        for i, source in enumerate(self._cameras):
            if source is current:
                self._camera_combo.selected_index = i + 1
                return
        self._camera_combo.selected_index = 0

    def _refresh_pipeline_combo(self) -> None:
        old = self._pipeline_combo.on_changed
        self._pipeline_combo.on_changed = None
        self._pipeline_combo.clear()
        self._pipeline_combo.add_item("(none)")
        self._pipeline_combo.add_item("(Default)")
        for name in self._rm.list_pipeline_names():
            self._pipeline_combo.add_item(name)
        self._pipeline_combo.on_changed = old

    def _select_current_pipeline(self) -> None:
        if self._render_target is None or self._render_target.pipeline is None:
            self._pipeline_combo.selected_index = 0
            return
        current = self._render_target.pipeline.name or ""
        for i in range(self._pipeline_combo.item_count):
            if self._pipeline_combo.item_text(i) == current:
                self._pipeline_combo.selected_index = i
                return
        self._pipeline_combo.selected_index = 1 if current == "Default" else 0

    def _on_enabled_changed(self, checked: bool) -> None:
        if self._updating or self._render_target is None:
            return
        self._render_target.enabled = bool(checked)
        self._emit_changed()

    def _on_kind_changed(self, index: int, _text: str) -> None:
        if self._updating or self._render_target is None:
            return
        if index < 0 or index >= len(self._target_kind_values):
            log.error(f"[RenderTargetInspector] invalid render target kind index: {index}")
            return
        kind = self._target_kind_values[index]
        self._render_target.kind = kind
        self._refresh_camera_combo()
        self._select_current_camera()
        self._update_kind_visibility()
        self._emit_changed()

    def _on_camera_changed(self, index: int, _text: str) -> None:
        if self._updating or self._render_target is None:
            return
        if index <= 0:
            if self._is_xr_target():
                self._render_target.xr_origin = None
            else:
                self._render_target.camera = None
            self._emit_changed()
            return
        idx = index - 1
        if 0 <= idx < len(self._cameras):
            if self._is_xr_target():
                self._render_target.xr_origin = self._cameras[idx]
            else:
                self._render_target.camera = self._cameras[idx]
            self._emit_changed()

    def _on_pipeline_changed(self, index: int, text: str) -> None:
        if self._updating or self._render_target is None:
            return
        if index == 0:
            self._render_target.pipeline = None
            self._refresh_pipeline_params()
            self._emit_changed()
            return

        if text == "(Default)":
            try:
                from termin.engine import RenderingManager
                self._render_target.pipeline = RenderingManager.instance().create_pipeline("Default")
                self._refresh_pipeline_params()
                self._emit_changed()
            except Exception as e:
                log.error(f"[RenderTargetInspector] create Default pipeline failed: {e}")
            return

        pipeline = self._rm.get_pipeline(text)
        if pipeline is None:
            log.error(f"[RenderTargetInspector] pipeline not found: {text}")
            return
        self._render_target.pipeline = pipeline
        self._refresh_pipeline_params()
        self._emit_changed()

    def _on_dynamic_resolution_changed(self, checked: bool) -> None:
        if self._updating or self._render_target is None:
            return
        self._render_target.dynamic_resolution = bool(checked)
        self._update_size_visibility()
        self._emit_changed()

    def _on_color_format_changed(self, index: int, _text: str) -> None:
        if self._updating or self._render_target is None:
            return
        if index < 0 or index >= len(self._color_format_values):
            log.error(f"[RenderTargetInspector] invalid color format index: {index}")
            return
        self._render_target.color_format = self._color_format_values[index]
        self._emit_changed()

    def _on_depth_format_changed(self, index: int, _text: str) -> None:
        if self._updating or self._render_target is None:
            return
        if index < 0 or index >= len(self._depth_format_values):
            log.error(f"[RenderTargetInspector] invalid depth format index: {index}")
            return
        self._render_target.depth_format = self._depth_format_values[index]
        self._emit_changed()

    def _on_clear_color_changed(self, checked: bool) -> None:
        if self._updating or self._render_target is None:
            return
        self._render_target.clear_color_enabled = bool(checked)
        self._emit_changed()

    def _on_clear_color_value_changed(self, _value: float) -> None:
        if self._updating or self._render_target is None:
            return
        self._render_target.clear_color_value = tuple(spin.value for spin in self._clear_color_spins)
        self._emit_changed()

    def _on_clear_depth_changed(self, checked: bool) -> None:
        if self._updating or self._render_target is None:
            return
        self._render_target.clear_depth_enabled = bool(checked)
        self._emit_changed()

    def _on_clear_depth_value_changed(self, _value: float) -> None:
        if self._updating or self._render_target is None:
            return
        self._render_target.clear_depth_value = float(self._clear_depth_value.value)
        self._emit_changed()

    def _on_size_changed(self, _value: float) -> None:
        if self._updating or self._render_target is None:
            return
        self._render_target.width = int(self._width.value)
        self._render_target.height = int(self._height.value)
        self._emit_changed()

    def _on_layer_mask_changed(self) -> None:
        if self._updating or self._render_target is None:
            return
        mask_str = self._layer_mask_widget.get_value()
        self._render_target.layer_mask = int(mask_str, 0)
        self._emit_changed()

    def _refresh_pipeline_params(self) -> None:
        """Rebuild pipeline parameter combos based on current pipeline's external params."""
        self._pipeline_params_grid.clear()
        self._pipeline_params_widgets.clear()
        self._pipeline_params_slots.clear()

        if self._render_target is None:
            self._hide_pipeline_params()
            return

        # Use pipeline name from the combo (the registered name), not from the
        # pipeline object (which may be a copy with a different/lost name).
        pipeline_name = self._pipeline_combo.selected_text
        if not pipeline_name or pipeline_name in ("(none)", "(Default)"):
            self._hide_pipeline_params()
            return

        asset = None
        try:
            asset = self._rm.get_pipeline_asset(pipeline_name)
            if asset is None:
                asset = self._rm.get_scene_pipeline_asset(pipeline_name)
        except Exception as e:
            log.warn(f"[RenderTargetInspector] Failed to get pipeline asset '{pipeline_name}': {e}")

        if asset is None:
            self._hide_pipeline_params()
            return

        slots = asset.external_params
        if not slots:
            self._hide_pipeline_params()
            return

        self._pipeline_params_sep.visible = True
        self._pipeline_params_title.visible = True
        self._pipeline_params_grid.visible = True

        params = self._render_target.pipeline_params

        for row_idx, slot in enumerate(slots):
            self._pipeline_params_slots.append(slot)
            lbl = Label()
            lbl.text = f"{slot}:"
            lbl.preferred_width = px(96)
            self._pipeline_params_grid.add(lbl, row_idx, 0)

            picker = TexturePickerWidget(
                self._rm,
                on_changed=lambda tag, val, s=slot: self._on_pipeline_param_changed(s, tag, val),
                scene_getter=self._scene_getter,
            )

            current_val = params.get(slot, "")
            if current_val:
                if current_val.startswith("file:"):
                    picker.set_value(self._texture_picker_name_from_file_ref(current_val), "file")
                else:
                    picker.set_value(current_val, "rt_color")
            else:
                picker.set_value("", "default")

            self._pipeline_params_grid.add(picker, row_idx, 1)
            self._pipeline_params_widgets.append(picker)

        if self._ui is not None:
            self._ui.request_layout()

    def _hide_pipeline_params(self) -> None:
        self._pipeline_params_sep.visible = False
        self._pipeline_params_title.visible = False
        self._pipeline_params_grid.visible = False

    def _on_pipeline_param_changed(self, slot: str, tag: str, value: str) -> None:
        if self._updating or self._render_target is None:
            return
        params = self._render_target.pipeline_params
        if tag == "default" or not value:
            params.pop(slot, None)
        elif tag == "file":
            file_ref = self._file_ref_from_texture_name(value)
            if file_ref is None:
                params.pop(slot, None)
            else:
                params[slot] = file_ref
        else:
            params[slot] = value
        self._render_target.pipeline_params = params
        self._emit_changed()

    def _texture_picker_name_from_file_ref(self, ref: str) -> str:
        """Resolve serialized file texture ref into TexturePicker asset name."""
        prefix = "file:"
        if not ref.startswith(prefix):
            return ref

        payload = ref[len(prefix):]
        asset = self._rm.get_texture_asset_by_uuid(payload)
        if asset is not None:
            return asset.name

        log.warn(
            "[RenderTargetInspector] texture file ref must be file:<uuid>; "
            f"asset uuid not found: {payload}"
        )
        return payload

    def _file_ref_from_texture_name(self, name: str) -> str | None:
        """Serialize TexturePicker asset name as file:<asset uuid>."""
        asset = self._rm.get_texture_asset(name)
        if asset is not None:
            return "file:" + asset.uuid

        asset = self._rm.get_texture_asset_by_uuid(name)
        if asset is not None:
            return "file:" + asset.uuid

        log.error(
            "[RenderTargetInspector] refusing to serialize texture pipeline param "
            f"without a known asset UUID: {name}"
        )
        return None

    def _update_size_visibility(self) -> None:
        texture_target = self._is_texture_target()
        manual = texture_target and not bool(self._dynamic_resolution.checked)
        self._width_lbl.visible = manual
        self._width.visible = manual
        self._height_lbl.visible = manual
        self._height.visible = manual
        if self._ui is not None:
            self._ui.request_layout()

    def _update_kind_visibility(self) -> None:
        has_target = self._render_target is not None
        texture_target = self._is_texture_target()
        self._camera_lbl.text = "Camera:" if texture_target else "XR Origin:"
        self._camera_lbl.visible = has_target
        self._camera_combo.visible = has_target
        self._dynamic_lbl.visible = texture_target
        self._dynamic_resolution.visible = texture_target
        self._color_format_lbl.visible = texture_target
        self._color_format.visible = texture_target
        self._depth_format_lbl.visible = texture_target
        self._depth_format.visible = texture_target
        self._update_size_visibility()

    def _is_texture_target(self) -> bool:
        return self._render_target is not None and self._render_target.kind == "texture_2d"

    def _is_xr_target(self) -> bool:
        return self._render_target is not None and self._render_target.kind == "xr_stereo"

    def _emit_changed(self) -> None:
        if self.on_changed is not None:
            self.on_changed()

    @staticmethod
    def _select_combo_value(combo: ComboBox, values: list[str], value: str) -> None:
        if value in values:
            combo.selected_index = values.index(value)
            return
        log.warn(f"[RenderTargetInspector] unknown render target format: {value}")
        combo.selected_index = 0

    @staticmethod
    def _target_kind_label(kind: str) -> str:
        for value, label in _TARGET_KINDS:
            if value == kind:
                return label
        log.warn(f"[RenderTargetInspector] unknown render target kind: {kind}")
        return "Texture 2D"
