"""Scene Properties dialog — configure background, ambient, skybox, pipelines."""

from __future__ import annotations

from typing import Callable

import numpy as np

from tcgui.widgets.dialog import Dialog
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.button import Button
from tcgui.widgets.combo_box import ComboBox
from tcgui.widgets.spin_box import SpinBox
from tcgui.widgets.list_widget import ListWidget
from tcgui.widgets.group_box import GroupBox
from tcgui.widgets.color_dialog import ColorDialog
from tcgui.widgets.units import px

from termin.editor.undo_stack import UndoCommand
from termin.visualization.core.scene import Scene
from tcbase import log


class ScenePropertyEditCommand(UndoCommand):
    """Undo command for editing scene properties."""

    def __init__(self, scene: Scene, property_name: str, old_value, new_value):
        self._scene = scene
        self._property_name = property_name
        self._old_value = self._clone(old_value)
        self._new_value = self._clone(new_value)

    def _clone(self, value):
        if isinstance(value, np.ndarray):
            return value.copy()
        return value

    def do(self) -> None:
        setattr(self._scene, self._property_name, self._clone(self._new_value))

    def undo(self) -> None:
        setattr(self._scene, self._property_name, self._clone(self._old_value))

    def merge_with(self, other: UndoCommand) -> bool:
        if not isinstance(other, ScenePropertyEditCommand):
            return False
        if other._scene is not self._scene:
            return False
        if other._property_name != self._property_name:
            return False
        self._new_value = self._clone(other._new_value)
        return True

    def __repr__(self) -> str:
        return f"ScenePropertyEditCommand({self._property_name})"


class SkyboxTypeEditCommand(UndoCommand):
    """Undo command for changing skybox type."""

    def __init__(self, scene: Scene, old_type: str, new_type: str):
        self._scene = scene
        self._old_type = old_type
        self._new_type = new_type

    def do(self) -> None:
        self._scene.set_skybox_type(self._new_type)

    def undo(self) -> None:
        self._scene.set_skybox_type(self._old_type)

    def __repr__(self) -> str:
        return f"SkyboxTypeEditCommand({self._old_type} -> {self._new_type})"


def _color_to_rgba255(value) -> tuple[int, int, int, int]:
    """Convert scene color (float 0-1 array/tuple) to (R,G,B,A) 0-255."""
    try:
        r = float(value[0])
        g = float(value[1])
        b = float(value[2])
        a = float(value[3]) if len(value) > 3 else 1.0
        return (
            int(max(0, min(255, r * 255))),
            int(max(0, min(255, g * 255))),
            int(max(0, min(255, b * 255))),
            int(max(0, min(255, a * 255))),
        )
    except Exception as e:
        log.error(f"Failed to convert color: {e}")
        return (255, 255, 255, 255)


def _rgba255_to_float3(rgba: tuple[int, int, int, int]) -> np.ndarray:
    """Convert (R,G,B,A) 0-255 to float32 array [r,g,b]."""
    return np.array([rgba[0] / 255.0, rgba[1] / 255.0, rgba[2] / 255.0], dtype=np.float32)


def _rgba255_to_float4(rgba: tuple[int, int, int, int]) -> np.ndarray:
    """Convert (R,G,B,A) 0-255 to float32 array [r,g,b,a]."""
    return np.array(
        [rgba[0] / 255.0, rgba[1] / 255.0, rgba[2] / 255.0, rgba[3] / 255.0],
        dtype=np.float32,
    )


def _make_color_button(color_rgba255: tuple[int, int, int, int]) -> Button:
    """Create a button showing current color as text."""
    btn = Button()
    r, g, b, a = color_rgba255
    btn.text = f"{r / 255:.2f}, {g / 255:.2f}, {b / 255:.2f}"
    btn.background_color = (r / 255, g / 255, b / 255, 1.0)
    btn.text_color = (1.0, 1.0, 1.0, 1.0) if (r + g + b) < 384 else (0.0, 0.0, 0.0, 1.0)
    btn.padding = 6
    return btn


def _update_color_button(btn: Button, rgba255: tuple[int, int, int, int]) -> None:
    """Update button appearance to show color."""
    r, g, b, a = rgba255
    btn.text = f"{r / 255:.2f}, {g / 255:.2f}, {b / 255:.2f}"
    btn.background_color = (r / 255, g / 255, b / 255, 1.0)
    btn.text_color = (1.0, 1.0, 1.0, 1.0) if (r + g + b) < 384 else (0.0, 0.0, 0.0, 1.0)


_SKYBOX_TYPES = [("Gradient", "gradient"), ("Solid Color", "solid"), ("None", "none")]


def show_scene_properties_dialog(
    ui,
    scene: Scene,
    push_undo_command: Callable[[UndoCommand, bool], None] | None = None,
    on_changed: Callable[[], None] | None = None,
) -> None:
    """Show scene properties dialog."""
    updating = [False]

    def _emit():
        if on_changed is not None:
            on_changed()

    content = VStack()
    content.spacing = 8

    title = Label()
    title.text = "Scene Properties"
    title.font_size = 14
    content.add_child(title)

    # --- Background ---
    bg_group = GroupBox()
    bg_group.title = "Background"
    bg_row = HStack()
    bg_row.spacing = 8
    bg_lbl = Label()
    bg_lbl.text = "Color:"
    bg_row.add_child(bg_lbl)

    bg_color = scene.background_color
    bg_btn = _make_color_button(_color_to_rgba255(bg_color))

    def _on_bg_color():
        current = scene.background_color
        initial = _color_to_rgba255(current)

        def _result(rgba):
            if rgba is None:
                return
            old_value = scene.background_color.copy()
            new_value = np.array(
                [rgba[0] / 255.0, rgba[1] / 255.0, rgba[2] / 255.0, float(current[3])],
                dtype=np.float32,
            )
            if push_undo_command is not None:
                cmd = ScenePropertyEditCommand(scene, "background_color", old_value, new_value)
                push_undo_command(cmd, False)
            else:
                scene.background_color = new_value
            _update_color_button(bg_btn, rgba)
            _emit()

        ColorDialog.pick_color(ui, initial=initial, show_alpha=False, on_result=_result)

    bg_btn.on_click = _on_bg_color
    bg_row.add_child(bg_btn)
    bg_group.add_child(bg_row)
    content.add_child(bg_group)

    # --- Ambient Lighting ---
    ambient_group = GroupBox()
    ambient_group.title = "Ambient Lighting"

    ambient_color_row = HStack()
    ambient_color_row.spacing = 8
    ambient_color_lbl = Label()
    ambient_color_lbl.text = "Color:"
    ambient_color_row.add_child(ambient_color_lbl)

    ambient_btn = _make_color_button(_color_to_rgba255(scene.ambient_color))

    def _on_ambient_color():
        current = scene.ambient_color
        initial = _color_to_rgba255(current)

        def _result(rgba):
            if rgba is None:
                return
            old_value = scene.ambient_color.copy()
            new_value = _rgba255_to_float3(rgba)
            if push_undo_command is not None:
                cmd = ScenePropertyEditCommand(scene, "ambient_color", old_value, new_value)
                push_undo_command(cmd, False)
            else:
                scene.ambient_color = new_value
            _update_color_button(ambient_btn, rgba)
            _emit()

        ColorDialog.pick_color(ui, initial=initial, show_alpha=False, on_result=_result)

    ambient_btn.on_click = _on_ambient_color
    ambient_color_row.add_child(ambient_btn)
    ambient_group.add_child(ambient_color_row)

    # Intensity
    intensity_row = HStack()
    intensity_row.spacing = 8
    intensity_lbl = Label()
    intensity_lbl.text = "Intensity:"
    intensity_row.add_child(intensity_lbl)

    intensity_spin = SpinBox()
    intensity_spin.value = scene.ambient_intensity
    intensity_spin.min_value = 0.0
    intensity_spin.max_value = 10.0
    intensity_spin.step = 0.01
    intensity_spin.decimals = 3

    def _on_intensity(val):
        if updating[0]:
            return
        old_value = scene.ambient_intensity
        if push_undo_command is not None:
            cmd = ScenePropertyEditCommand(scene, "ambient_intensity", old_value, val)
            push_undo_command(cmd, True)
        else:
            scene.ambient_intensity = val
        _emit()

    intensity_spin.on_value_changed = _on_intensity
    intensity_row.add_child(intensity_spin)
    ambient_group.add_child(intensity_row)
    content.add_child(ambient_group)

    # --- Skybox ---
    skybox_group = GroupBox()
    skybox_group.title = "Skybox"

    # Type combo
    type_row = HStack()
    type_row.spacing = 8
    type_lbl = Label()
    type_lbl.text = "Type:"
    type_row.add_child(type_lbl)

    skybox_combo = ComboBox()
    skybox_combo.items = [label for label, _ in _SKYBOX_TYPES]
    current_skybox = scene.skybox_type
    for i, (_, val) in enumerate(_SKYBOX_TYPES):
        if val == current_skybox:
            skybox_combo.selected_index = i
            break
    type_row.add_child(skybox_combo)
    skybox_group.add_child(type_row)

    # Solid color row
    solid_row = HStack()
    solid_row.spacing = 8
    solid_lbl = Label()
    solid_lbl.text = "Color:"
    solid_row.add_child(solid_lbl)

    skybox_color_btn = _make_color_button(_color_to_rgba255(scene.skybox_color))

    def _on_skybox_color():
        initial = _color_to_rgba255(scene.skybox_color)

        def _result(rgba):
            if rgba is None:
                return
            old_value = scene.skybox_color.copy()
            new_value = _rgba255_to_float3(rgba)
            if push_undo_command is not None:
                cmd = ScenePropertyEditCommand(scene, "skybox_color", old_value, new_value)
                push_undo_command(cmd, False)
            else:
                scene.skybox_color = new_value
            _update_color_button(skybox_color_btn, rgba)
            _emit()

        ColorDialog.pick_color(ui, initial=initial, show_alpha=False, on_result=_result)

    skybox_color_btn.on_click = _on_skybox_color
    solid_row.add_child(skybox_color_btn)
    skybox_group.add_child(solid_row)

    # Gradient top
    top_row = HStack()
    top_row.spacing = 8
    top_lbl = Label()
    top_lbl.text = "Top:"
    top_row.add_child(top_lbl)

    skybox_top_btn = _make_color_button(_color_to_rgba255(scene.skybox_top_color))

    def _on_skybox_top_color():
        initial = _color_to_rgba255(scene.skybox_top_color)

        def _result(rgba):
            if rgba is None:
                return
            old_value = scene.skybox_top_color.copy()
            new_value = _rgba255_to_float3(rgba)
            if push_undo_command is not None:
                cmd = ScenePropertyEditCommand(scene, "skybox_top_color", old_value, new_value)
                push_undo_command(cmd, False)
            else:
                scene.skybox_top_color = new_value
            _update_color_button(skybox_top_btn, rgba)
            _emit()

        ColorDialog.pick_color(ui, initial=initial, show_alpha=False, on_result=_result)

    skybox_top_btn.on_click = _on_skybox_top_color
    top_row.add_child(skybox_top_btn)
    skybox_group.add_child(top_row)

    # Gradient bottom
    bottom_row = HStack()
    bottom_row.spacing = 8
    bottom_lbl = Label()
    bottom_lbl.text = "Bottom:"
    bottom_row.add_child(bottom_lbl)

    skybox_bottom_btn = _make_color_button(_color_to_rgba255(scene.skybox_bottom_color))

    def _on_skybox_bottom_color():
        initial = _color_to_rgba255(scene.skybox_bottom_color)

        def _result(rgba):
            if rgba is None:
                return
            old_value = scene.skybox_bottom_color.copy()
            new_value = _rgba255_to_float3(rgba)
            if push_undo_command is not None:
                cmd = ScenePropertyEditCommand(scene, "skybox_bottom_color", old_value, new_value)
                push_undo_command(cmd, False)
            else:
                scene.skybox_bottom_color = new_value
            _update_color_button(skybox_bottom_btn, rgba)
            _emit()

        ColorDialog.pick_color(ui, initial=initial, show_alpha=False, on_result=_result)

    skybox_bottom_btn.on_click = _on_skybox_bottom_color
    bottom_row.add_child(skybox_bottom_btn)
    skybox_group.add_child(bottom_row)

    # Update visibility based on skybox type
    def _update_skybox_visibility():
        skybox_type = _SKYBOX_TYPES[skybox_combo.selected_index][1]
        solid_row.visible = (skybox_type == "solid")
        top_row.visible = (skybox_type == "gradient")
        bottom_row.visible = (skybox_type == "gradient")

    _update_skybox_visibility()

    def _on_skybox_type(idx):
        if updating[0]:
            return
        new_type = _SKYBOX_TYPES[idx][1]
        old_type = scene.skybox_type
        if new_type == old_type:
            return
        if push_undo_command is not None:
            cmd = SkyboxTypeEditCommand(scene, old_type, new_type)
            push_undo_command(cmd, False)
        else:
            scene.set_skybox_type(new_type)
        _update_skybox_visibility()
        _emit()

    skybox_combo.on_selection_changed = _on_skybox_type
    content.add_child(skybox_group)

    # --- Scene Pipelines ---
    pipelines_group = GroupBox()
    pipelines_group.title = "Scene Pipelines"

    pipelines_list = ListWidget()
    pipelines_list.preferred_height = px(100)
    pipelines_list.item_height = 24

    # Store template handles for removal
    pipeline_handles: list = []

    def _refresh_pipelines():
        pipeline_handles.clear()
        items = []
        for template in scene.scene_pipelines:
            if template.is_valid:
                name = template.name
                uuid_short = template.uuid[:8] if template.uuid else ""
                items.append({"text": f"{name} ({uuid_short}...)"})
            else:
                items.append({"text": "(missing pipeline)"})
            pipeline_handles.append(template)
        pipelines_list.set_items(items)
        remove_btn.enabled = False

    remove_btn = Button()
    remove_btn.text = "Remove"
    remove_btn.padding = 6
    remove_btn.enabled = False

    def _on_pipeline_select(idx, item):
        remove_btn.enabled = (idx >= 0)

    pipelines_list.on_select = _on_pipeline_select

    add_btn = Button()
    add_btn.text = "Add..."
    add_btn.padding = 6

    def _on_add_pipeline():
        from termin.assets.resources import ResourceManager

        rm = ResourceManager.instance()
        if rm is None:
            return

        pipeline_names = rm.list_scene_pipeline_names()
        if not pipeline_names:
            from tcgui.widgets.message_box import MessageBox
            MessageBox.show_info(ui, "No Pipelines",
                                 "No scene pipelines are registered.")
            return

        existing_uuids = set()
        for template in scene.scene_pipelines:
            if template.is_valid:
                existing_uuids.add(template.uuid)

        available = []
        for name in pipeline_names:
            asset = rm.get_scene_pipeline_asset(name)
            if asset is not None and asset.uuid not in existing_uuids:
                available.append(name)

        if not available:
            from tcgui.widgets.message_box import MessageBox
            MessageBox.show_info(ui, "No Pipelines",
                                 "All available pipelines are already added.")
            return

        from tcgui.widgets.input_dialog import show_input_dialog

        # Use combo-style selection via a simple list dialog
        selection_list = ListWidget()
        selection_list.set_items([{"text": n} for n in available])
        selection_list.selected_index = 0
        selection_list.preferred_height = px(150)

        sel_dlg = Dialog()
        sel_dlg.title = "Add Scene Pipeline"
        sel_dlg.content = selection_list
        sel_dlg.buttons = ["OK", "Cancel"]
        sel_dlg.default_button = "OK"
        sel_dlg.cancel_button = "Cancel"
        sel_dlg.min_width = 350

        def _on_sel_result(btn):
            if btn != "OK":
                return
            idx = selection_list.selected_index
            if idx < 0 or idx >= len(available):
                return
            name = available[idx]
            asset = rm.get_scene_pipeline_asset(name)
            if asset is None:
                return
            scene.add_scene_pipeline(asset.template)
            _refresh_pipelines()
            _emit()

        sel_dlg.on_result = _on_sel_result
        sel_dlg.show(ui)

    add_btn.on_click = _on_add_pipeline

    def _on_remove_pipeline():
        idx = pipelines_list.selected_index
        if idx < 0 or idx >= len(pipeline_handles):
            return
        handle = pipeline_handles[idx]
        scene.remove_scene_pipeline(handle)
        _refresh_pipelines()
        _emit()

    remove_btn.on_click = _on_remove_pipeline

    pipelines_group.add_child(pipelines_list)
    btn_row = HStack()
    btn_row.spacing = 4
    btn_row.add_child(add_btn)
    btn_row.add_child(remove_btn)
    pipelines_group.add_child(btn_row)

    _refresh_pipelines()
    content.add_child(pipelines_group)

    # --- Dialog ---
    dlg = Dialog()
    dlg.title = "Scene Properties"
    dlg.content = content
    dlg.buttons = ["Close"]
    dlg.default_button = "Close"
    dlg.cancel_button = "Close"
    dlg.min_width = 450

    dlg.show(ui, windowed=True)
