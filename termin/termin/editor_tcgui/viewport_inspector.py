"""Viewport inspector for tcgui."""

from __future__ import annotations

from typing import Callable, Optional

from tcbase import log
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.grid_layout import GridLayout
from tcgui.widgets.label import Label
from tcgui.widgets.combo_box import ComboBox
from tcgui.widgets.checkbox import Checkbox
from tcgui.widgets.spin_box import SpinBox
from tcgui.widgets.separator import Separator
from tcgui.widgets.units import px


class ViewportInspectorTcgui(VStack):
    """Inspector panel for Viewport properties."""

    def __init__(self, resource_manager) -> None:
        super().__init__()
        self.spacing = 4

        self._rm = resource_manager
        self._viewport = None
        self._scene = None
        self._displays = []
        self._current_display = None
        self._cameras = []
        self._updating = False
        self.on_changed: Optional[Callable[[], None]] = None

        title = Label()
        title.text = "Viewport Inspector"
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

        self._enabled = Checkbox()
        self._enabled.on_changed = self._on_enabled_changed
        enabled_lbl = Label(); enabled_lbl.text = "Enabled:"; enabled_lbl.preferred_width = px(96)
        grid.add(enabled_lbl, 0, 0)
        grid.add(self._enabled, 0, 1)

        display_lbl = Label(); display_lbl.text = "Display:"; display_lbl.preferred_width = px(96)
        grid.add(display_lbl, 1, 0)
        self._display_combo = ComboBox()
        self._display_combo.on_changed = self._on_display_changed
        grid.add(self._display_combo, 1, 1)

        cam_lbl = Label(); cam_lbl.text = "Camera:"; cam_lbl.preferred_width = px(96)
        grid.add(cam_lbl, 2, 0)
        self._camera_combo = ComboBox()
        self._camera_combo.on_changed = self._on_camera_changed
        grid.add(self._camera_combo, 2, 1)

        pipe_lbl = Label(); pipe_lbl.text = "Pipeline:"; pipe_lbl.preferred_width = px(96)
        grid.add(pipe_lbl, 3, 0)
        self._pipeline_combo = ComboBox()
        self._pipeline_combo.on_changed = self._on_pipeline_changed
        grid.add(self._pipeline_combo, 3, 1)

        rect_title = Label()
        rect_title.text = "Rect (0..1)"
        self.add_child(rect_title)

        rect_row = HStack()
        rect_row.spacing = 4
        self._x = self._make_rect_spin()
        self._y = self._make_rect_spin()
        self._w = self._make_rect_spin(default=1.0)
        self._h = self._make_rect_spin(default=1.0)
        for sb in (self._x, self._y, self._w, self._h):
            rect_row.add_child(sb)
        self.add_child(rect_row)

        depth_row = HStack()
        depth_row.spacing = 6
        depth_lbl = Label(); depth_lbl.text = "Depth:"; depth_lbl.preferred_width = px(96)
        self._depth = SpinBox()
        self._depth.decimals = 0
        self._depth.min_value = -1000
        self._depth.max_value = 1000
        self._depth.on_changed = self._on_depth_changed
        depth_row.add_child(depth_lbl)
        depth_row.add_child(self._depth)
        self.add_child(depth_row)

        self._empty = Label()
        self._empty.text = "No viewport selected."
        self._empty.color = (0.52, 0.56, 0.62, 1.0)
        self.add_child(self._empty)

        self._set_visible_state(False)

    def _make_rect_spin(self, default: float = 0.0) -> SpinBox:
        sb = SpinBox()
        sb.decimals = 3
        sb.step = 0.05
        sb.min_value = 0.0
        sb.max_value = 1.0
        sb.value = default
        sb.on_changed = self._on_rect_changed
        sb.stretch = True
        return sb

    def set_displays(self, displays, display_names: Optional[dict] = None) -> None:
        self._displays = list(displays or [])
        self._refresh_display_combo(display_names or {})

    def set_scene(self, scene) -> None:
        self._scene = scene
        self._refresh_camera_combo()

    def set_viewport(self, viewport=None, current_display=None) -> None:
        self._viewport = viewport
        self._current_display = current_display

        self._updating = True
        try:
            if viewport is None:
                self._set_visible_state(False)
                return

            self._set_visible_state(True)
            vp_name = viewport.name or "<unnamed>"
            self._subtitle.text = f"Viewport: {vp_name}"

            self._enabled.checked = bool(viewport.enabled)
            self._refresh_display_combo({})
            if current_display is not None:
                idx = self._find_display_index(current_display)
                self._display_combo.selected_index = idx

            self._refresh_camera_combo()
            self._select_current_camera()
            self._refresh_pipeline_combo()
            self._select_current_pipeline()

            x, y, w, h = viewport.rect
            self._x.value = float(x)
            self._y.value = float(y)
            self._w.value = float(w)
            self._h.value = float(h)
            self._depth.value = int(viewport.depth)
        finally:
            self._updating = False
            if self._ui is not None:
                self._ui.request_layout()

    def _set_visible_state(self, has_viewport: bool) -> None:
        self._enabled.visible = has_viewport
        self._display_combo.visible = has_viewport
        self._camera_combo.visible = has_viewport
        self._pipeline_combo.visible = has_viewport
        self._x.visible = has_viewport
        self._y.visible = has_viewport
        self._w.visible = has_viewport
        self._h.visible = has_viewport
        self._depth.visible = has_viewport
        self._empty.visible = not has_viewport

    def _refresh_display_combo(self, display_names: dict) -> None:
        old = self._display_combo.on_changed
        self._display_combo.on_changed = None
        self._display_combo.clear()
        for disp in self._displays:
            name = display_names.get(disp.tc_display_ptr, None)
            self._display_combo.add_item(name or disp.name or "Display")
        self._display_combo.on_changed = old

    def _find_display_index(self, display) -> int:
        for i, disp in enumerate(self._displays):
            if disp is display:
                return i
        return -1

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
                log.error(f"[ViewportInspectorTcgui] camera scan failed: {e}")

        self._camera_combo.on_changed = old

    def _select_current_camera(self) -> None:
        if self._viewport is None or self._viewport.camera is None:
            self._camera_combo.selected_index = 0
            return
        for i, cam in enumerate(self._cameras):
            if cam is self._viewport.camera:
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
        if self._viewport is None or self._viewport.pipeline is None:
            self._pipeline_combo.selected_index = 0
            return
        current = self._viewport.pipeline.name or ""
        for i in range(self._pipeline_combo.item_count):
            if self._pipeline_combo.item_text(i) == current:
                self._pipeline_combo.selected_index = i
                return
        self._pipeline_combo.selected_index = 1 if current == "Default" else 0

    def _on_enabled_changed(self, checked: bool) -> None:
        if self._updating or self._viewport is None:
            return
        self._viewport.enabled = bool(checked)
        self._emit_changed()

    def _on_display_changed(self, index: int, _text: str) -> None:
        if self._updating or self._viewport is None:
            return
        if index < 0 or index >= len(self._displays):
            return
        target = self._displays[index]
        old_display = self._current_display
        if target is old_display or old_display is None:
            return

        try:
            old_display.remove_viewport(self._viewport)
            target.add_viewport(self._viewport)
            self._current_display = target
            self._emit_changed()
        except Exception as e:
            log.error(f"[ViewportInspectorTcgui] failed to move viewport between displays: {e}")

    def _on_camera_changed(self, index: int, _text: str) -> None:
        if self._updating or self._viewport is None:
            return
        if index <= 0:
            self._viewport.camera = None
            self._emit_changed()
            return
        idx = index - 1
        if 0 <= idx < len(self._cameras):
            self._viewport.camera = self._cameras[idx]
            self._emit_changed()

    def _on_pipeline_changed(self, index: int, text: str) -> None:
        if self._updating or self._viewport is None:
            return
        if index == 0:
            self._viewport.pipeline = None
            self._emit_changed()
            return

        if text == "(Default)":
            try:
                from termin.visualization.core.viewport import make_default_pipeline
                self._viewport.pipeline = make_default_pipeline()
                self._emit_changed()
            except Exception as e:
                log.error(f"[ViewportInspectorTcgui] make_default_pipeline failed: {e}")
            return

        pipeline = self._rm.get_pipeline(text)
        if pipeline is None:
            log.error(f"[ViewportInspectorTcgui] pipeline not found: {text}")
            return
        self._viewport.pipeline = pipeline
        self._emit_changed()

    def _on_rect_changed(self, _value: float) -> None:
        if self._updating or self._viewport is None:
            return
        self._viewport.rect = (self._x.value, self._y.value, self._w.value, self._h.value)
        self._emit_changed()

    def _on_depth_changed(self, _value: float) -> None:
        if self._updating or self._viewport is None:
            return
        self._viewport.depth = int(self._depth.value)
        self._emit_changed()

    def _emit_changed(self) -> None:
        if self.on_changed is not None:
            self.on_changed()
