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
    """Inspector panel for Viewport properties.

    Viewport-owned RenderTarget properties are shown in a separate
    section so users don't have to pick an unrelated target from the
    global pool.
    """

    def __init__(self, resource_manager) -> None:
        super().__init__()
        self.spacing = 4

        self._rm = resource_manager
        self._viewport = None
        self._scene = None
        self._scenes: list = []
        self._cameras: list = []
        self._displays = []
        self._current_display = None
        self._updating = False
        self.on_changed: Optional[Callable[[], None]] = None
        self._scene_getter: Optional[Callable[[], list]] = None

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
        self._viewport_grid = grid
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

        scene_lbl = Label(); scene_lbl.text = "Scene:"; scene_lbl.preferred_width = px(96)
        grid.add(scene_lbl, 2, 0)
        self._scene_combo = ComboBox()
        self._scene_combo.on_changed = self._on_scene_changed
        grid.add(self._scene_combo, 2, 1)

        input_mode_lbl = Label(); input_mode_lbl.text = "Input Mode:"; input_mode_lbl.preferred_width = px(96)
        grid.add(input_mode_lbl, 3, 0)
        self._input_mode_combo = ComboBox()
        self._input_mode_combo.add_item("none")
        self._input_mode_combo.add_item("simple")
        self._input_mode_combo.add_item("editor")
        self._input_mode_combo.on_changed = self._on_input_mode_changed
        grid.add(self._input_mode_combo, 3, 1)

        block_lbl = Label(); block_lbl.text = "Block in Editor:"; block_lbl.preferred_width = px(96)
        grid.add(block_lbl, 4, 0)
        self._block_input = Checkbox()
        self._block_input.on_changed = self._on_block_input_changed
        grid.add(self._block_input, 4, 1)

        rect_title = Label()
        rect_title.text = "Rect (0..1)"
        self._rect_title = rect_title
        self.add_child(self._rect_title)

        rect_row = HStack()
        rect_row.spacing = 4
        self._rect_row = rect_row
        self._x = self._make_rect_spin()
        self._y = self._make_rect_spin()
        self._w = self._make_rect_spin(default=1.0)
        self._h = self._make_rect_spin(default=1.0)
        for sb in (self._x, self._y, self._w, self._h):
            self._rect_row.add_child(sb)
        self.add_child(self._rect_row)

        depth_row = HStack()
        depth_row.spacing = 6
        self._depth_row = depth_row
        depth_lbl = Label(); depth_lbl.text = "Depth:"; depth_lbl.preferred_width = px(96)
        self._depth = SpinBox()
        self._depth.decimals = 0
        self._depth.min_value = -1000
        self._depth.max_value = 1000
        self._depth.on_changed = self._on_depth_changed
        self._depth_row.add_child(depth_lbl)
        self._depth_row.add_child(self._depth)
        self.add_child(self._depth_row)

        self._rt_separator = Separator()
        self.add_child(self._rt_separator)
        rt_title = Label()
        rt_title.text = "Render Target"
        self._rt_title = rt_title
        self.add_child(self._rt_title)

        rt_grid = GridLayout(columns=2)
        rt_grid.column_spacing = 4
        rt_grid.row_spacing = 4
        rt_grid.set_column_stretch(1, 1.0)
        self._rt_grid = rt_grid
        self.add_child(self._rt_grid)

        cam_lbl = Label(); cam_lbl.text = "Camera:"; cam_lbl.preferred_width = px(96)
        self._camera_combo = ComboBox()
        self._camera_combo.on_changed = self._on_camera_changed
        rt_grid.add(cam_lbl, 0, 0)
        rt_grid.add(self._camera_combo, 0, 1)

        pipe_lbl = Label(); pipe_lbl.text = "Pipeline:"; pipe_lbl.preferred_width = px(96)
        self._pipeline_combo = ComboBox()
        self._pipeline_combo.on_changed = self._on_pipeline_changed
        rt_grid.add(pipe_lbl, 1, 0)
        rt_grid.add(self._pipeline_combo, 1, 1)

        use_view_lbl = Label(); use_view_lbl.text = "Use View Size:"; use_view_lbl.preferred_width = px(96)
        self._use_view_size = Checkbox()
        self._use_view_size.on_changed = self._on_use_view_size_changed
        rt_grid.add(use_view_lbl, 2, 0)
        rt_grid.add(self._use_view_size, 2, 1)

        width_lbl = Label(); width_lbl.text = "Width:"; width_lbl.preferred_width = px(96)
        self._width_lbl = width_lbl
        self._width = SpinBox()
        self._width.decimals = 0
        self._width.step = 64
        self._width.min_value = 1
        self._width.max_value = 8192
        self._width.on_changed = self._on_size_changed
        rt_grid.add(self._width_lbl, 3, 0)
        rt_grid.add(self._width, 3, 1)

        height_lbl = Label(); height_lbl.text = "Height:"; height_lbl.preferred_width = px(96)
        self._height_lbl = height_lbl
        self._height = SpinBox()
        self._height.decimals = 0
        self._height.step = 64
        self._height.min_value = 1
        self._height.max_value = 8192
        self._height.on_changed = self._on_size_changed
        rt_grid.add(self._height_lbl, 4, 0)
        rt_grid.add(self._height, 4, 1)

        self._empty = Label()
        self._empty.text = "No viewport selected."
        self._empty.color = (0.52, 0.56, 0.62, 1.0)
        self.add_child(self._empty)

        self._interactive_widgets = [
            self._viewport_grid,
            self._rect_title,
            self._rect_row,
            self._depth_row,
            self._rt_separator,
            self._rt_title,
            self._rt_grid,
        ]
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

    def set_scenes(self, scenes: list) -> None:
        self._scenes = list(scenes)
        self._refresh_scene_combo()
        self._select_current_scene()

    def set_scene_getter(self, getter: Callable[[], list]) -> None:
        self._scene_getter = getter

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

            self._refresh_scene_combo()
            self._select_current_scene()
            self._refresh_camera_combo()
            self._select_current_camera()
            self._refresh_pipeline_combo()
            self._select_current_pipeline()

            mode = viewport.input_mode or "none"
            for i in range(self._input_mode_combo.item_count):
                if self._input_mode_combo.item_text(i) == mode:
                    self._input_mode_combo.selected_index = i
                    break
            self._block_input.checked = bool(viewport.block_input_in_editor)

            x, y, w, h = viewport.rect
            self._x.value = float(x)
            self._y.value = float(y)
            self._w.value = float(w)
            self._h.value = float(h)
            self._depth.value = int(viewport.depth)

            rt = viewport.render_target
            self._use_view_size.checked = bool(viewport.override_resolution)
            if rt is not None:
                self._width.value = int(rt.width)
                self._height.value = int(rt.height)
            self._update_size_visibility()
        finally:
            self._updating = False
            if self._ui is not None:
                self._ui.request_layout()

    def _set_visible_state(self, has_viewport: bool) -> None:
        for w in self._interactive_widgets:
            w.visible = has_viewport
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

    def _refresh_scene_combo(self) -> None:
        old = self._scene_combo.on_changed
        self._scene_combo.on_changed = None
        self._scene_combo.clear()
        if self._scene_getter is not None:
            try:
                self._scenes = list(self._scene_getter())
            except Exception as e:
                log.error(f"[ViewportInspectorTcgui] scene scan failed: {e}")
                self._scenes = []
        for scene in self._scenes:
            self._scene_combo.add_item(scene.name or "(unnamed)")
        self._scene_combo.on_changed = old

    def _select_current_scene(self) -> None:
        if self._viewport is None:
            self._scene_combo.selected_index = -1
            return
        vp_scene = self._viewport.scene
        if vp_scene is None:
            self._scene_combo.selected_index = -1
            return
        for i, scene in enumerate(self._scenes):
            if scene.equal(vp_scene):
                self._scene_combo.selected_index = i
                return
        self._scene_combo.selected_index = -1

    def _on_scene_changed(self, index: int, _text: str) -> None:
        if self._updating or self._viewport is None:
            return
        if 0 <= index < len(self._scenes):
            self._viewport.scene = self._scenes[index]
            self._viewport.camera = None
            self._refresh_camera_combo()
            self._camera_combo.selected_index = 0
            self._emit_changed()

    def _refresh_camera_combo(self) -> None:
        old = self._camera_combo.on_changed
        self._camera_combo.on_changed = None
        self._camera_combo.clear()
        self._cameras.clear()

        self._camera_combo.add_item("(none)")
        scene = self._viewport.scene if self._viewport is not None else self._scene
        if scene is not None:
            try:
                from termin.visualization.core.camera import CameraComponent
                for ent in scene.entities:
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

    def _on_use_view_size_changed(self, checked: bool) -> None:
        if self._updating or self._viewport is None:
            return
        self._viewport.override_resolution = bool(checked)
        self._update_size_visibility()
        self._emit_changed()

    def _on_size_changed(self, _value: float) -> None:
        if self._updating or self._viewport is None:
            return
        rt = self._viewport.render_target
        if rt is None:
            return
        rt.width = int(self._width.value)
        rt.height = int(self._height.value)
        self._emit_changed()

    def _update_size_visibility(self) -> None:
        manual = not bool(self._use_view_size.checked)
        self._width_lbl.visible = manual
        self._width.visible = manual
        self._height_lbl.visible = manual
        self._height.visible = manual

    def _on_input_mode_changed(self, _index: int, text: str) -> None:
        if self._updating or self._viewport is None:
            return
        self._viewport.input_mode = text
        self._emit_changed()

    def _on_block_input_changed(self, checked: bool) -> None:
        if self._updating or self._viewport is None:
            return
        self._viewport.block_input_in_editor = bool(checked)
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
