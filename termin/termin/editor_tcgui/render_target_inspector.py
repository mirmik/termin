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


class RenderTargetInspectorTcgui(VStack):
    """Inspector panel for RenderTarget properties."""

    def __init__(self, resource_manager) -> None:
        super().__init__()
        self.spacing = 4

        self._rm = resource_manager
        self._render_target = None
        self._scene = None
        self._cameras = []
        self._updating = False
        self.on_changed: Optional[Callable[[], None]] = None

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
        self._enabled = Checkbox()
        self._enabled.on_changed = self._on_enabled_changed
        grid.add(enabled_lbl, 0, 0)
        grid.add(self._enabled, 0, 1)

        cam_lbl = Label(); cam_lbl.text = "Camera:"; cam_lbl.preferred_width = px(96)
        self._camera_combo = ComboBox()
        self._camera_combo.on_changed = self._on_camera_changed
        grid.add(cam_lbl, 1, 0)
        grid.add(self._camera_combo, 1, 1)

        pipe_lbl = Label(); pipe_lbl.text = "Pipeline:"; pipe_lbl.preferred_width = px(96)
        self._pipeline_combo = ComboBox()
        self._pipeline_combo.on_changed = self._on_pipeline_changed
        grid.add(pipe_lbl, 2, 0)
        grid.add(self._pipeline_combo, 2, 1)

        width_lbl = Label(); width_lbl.text = "Width:"; width_lbl.preferred_width = px(96)
        self._width = SpinBox()
        self._width.decimals = 0
        self._width.step = 64
        self._width.min_value = 1
        self._width.max_value = 8192
        self._width.value = 512
        self._width.on_changed = self._on_size_changed
        grid.add(width_lbl, 3, 0)
        grid.add(self._width, 3, 1)

        height_lbl = Label(); height_lbl.text = "Height:"; height_lbl.preferred_width = px(96)
        self._height = SpinBox()
        self._height.decimals = 0
        self._height.step = 64
        self._height.min_value = 1
        self._height.max_value = 8192
        self._height.value = 512
        self._height.on_changed = self._on_size_changed
        grid.add(height_lbl, 4, 0)
        grid.add(self._height, 4, 1)

        self._empty = Label()
        self._empty.text = "No render target selected."
        self._empty.color = (0.52, 0.56, 0.62, 1.0)
        self.add_child(self._empty)

        self._set_visible_state(False)

    def set_scene(self, scene) -> None:
        self._scene = scene
        self._refresh_camera_combo()

    def set_render_target(self, render_target=None) -> None:
        self._render_target = render_target

        self._updating = True
        try:
            if render_target is None:
                self._set_visible_state(False)
                return

            self._set_visible_state(True)
            rt_name = render_target.name or "<unnamed>"
            self._subtitle.text = f"Render Target: {rt_name}"

            self._enabled.checked = bool(render_target.enabled)

            self._refresh_camera_combo()
            self._select_current_camera()
            self._refresh_pipeline_combo()
            self._select_current_pipeline()

            self._width.value = render_target.width
            self._height.value = render_target.height
        finally:
            self._updating = False
            if self._ui is not None:
                self._ui.request_layout()

    def _set_visible_state(self, has_target: bool) -> None:
        self._enabled.visible = has_target
        self._camera_combo.visible = has_target
        self._pipeline_combo.visible = has_target
        self._width.visible = has_target
        self._height.visible = has_target
        self._empty.visible = not has_target

    def _refresh_camera_combo(self) -> None:
        old = self._camera_combo.on_changed
        self._camera_combo.on_changed = None
        self._camera_combo.clear()
        self._cameras.clear()

        self._camera_combo.add_item("(none)")
        if self._scene is not None:
            try:
                from termin.visualization.core.camera import CameraComponent
                for ent in self._scene.entities:
                    cam = ent.get_component(CameraComponent)
                    if cam is None:
                        continue
                    label = ent.name or ent.uuid or "Camera"
                    self._cameras.append(cam)
                    self._camera_combo.add_item(label)
            except Exception as e:
                log.error(f"[RenderTargetInspector] camera scan failed: {e}")

        self._camera_combo.on_changed = old

    def _select_current_camera(self) -> None:
        if self._render_target is None or self._render_target.camera is None:
            self._camera_combo.selected_index = 0
            return
        for i, cam in enumerate(self._cameras):
            if cam is self._render_target.camera:
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

    def _on_camera_changed(self, index: int, _text: str) -> None:
        if self._updating or self._render_target is None:
            return
        if index <= 0:
            self._render_target.camera = None
            self._emit_changed()
            return
        idx = index - 1
        if 0 <= idx < len(self._cameras):
            self._render_target.camera = self._cameras[idx]
            self._emit_changed()

    def _on_pipeline_changed(self, index: int, text: str) -> None:
        if self._updating or self._render_target is None:
            return
        if index == 0:
            self._render_target.pipeline = None
            self._emit_changed()
            return

        if text == "(Default)":
            try:
                from termin.visualization.core.viewport import make_default_pipeline
                self._render_target.pipeline = make_default_pipeline()
                self._emit_changed()
            except Exception as e:
                log.error(f"[RenderTargetInspector] make_default_pipeline failed: {e}")
            return

        pipeline = self._rm.get_pipeline(text)
        if pipeline is None:
            log.error(f"[RenderTargetInspector] pipeline not found: {text}")
            return
        self._render_target.pipeline = pipeline
        self._emit_changed()

    def _on_size_changed(self, _value: float) -> None:
        if self._updating or self._render_target is None:
            return
        self._render_target.width = int(self._width.value)
        self._render_target.height = int(self._height.value)
        self._emit_changed()

    def _emit_changed(self) -> None:
        if self.on_changed is not None:
            self.on_changed()
