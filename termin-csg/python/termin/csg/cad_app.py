"""Standalone mini CAD application for procedural CSG documents."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import sdl2

from tcbase import Key, Mods, MouseButton, log
from tcgui.widgets.button import Button
from tcgui.widgets.checkbox import Checkbox
from tcgui.widgets.file_dialog_overlay import show_open_file_dialog, show_save_file_dialog
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.menu import Menu, MenuItem
from tcgui.widgets.menu_bar import MenuBar
from tcgui.widgets.panel import Panel
from tcgui.widgets.separator import Separator
from tcgui.widgets.splitter import Splitter
from tcgui.widgets.spin_box import SpinBox
from tcgui.widgets.tree import TreeNode, TreeWidget
from tcgui.widgets.ui import UI
from tcgui.widgets.units import px
from tcgui.widgets.vstack import VStack
from termin.display import SDLBackendWindow
from tgfx import Tgfx2Context

from termin.csg.cad_viewer import CadViewportWidget, CsgSceneRenderer, document_bounds
from termin.csg.cad_state import CAD_STATE_FILTER, CadState, load_cad_state, save_cad_state
from termin.csg.document_edit import SketchDraft
from termin.csg.document_eval import extrude_vector_for_operation
from termin.csg.editor_controller import CsgEditorCommandResult, CsgEditorController
from termin.csg.document_raycast import ray_plane_intersection
from termin.csg.document_tree_model import DocumentTreeNode, build_document_tree, document_summary
from termin.csg.procedural_document import (
    BOOLEAN_OPERATION_KINDS,
    CONTOUR_ROLE_HOLE,
    CONTOUR_ROLE_OUTER,
    PRIMITIVE_OPERATION_KIND,
    ProceduralMeshDocument,
    ProceduralPlane,
)
from termin.csg.viewer_camera import OrbitCamera


_SDL_BUTTON_MAP = {1: MouseButton.LEFT, 2: MouseButton.MIDDLE, 3: MouseButton.RIGHT}
_KEY_MAP = {
    sdl2.SDL_SCANCODE_BACKSPACE: Key.BACKSPACE,
    sdl2.SDL_SCANCODE_DELETE: Key.DELETE,
    sdl2.SDL_SCANCODE_LEFT: Key.LEFT,
    sdl2.SDL_SCANCODE_RIGHT: Key.RIGHT,
    sdl2.SDL_SCANCODE_UP: Key.UP,
    sdl2.SDL_SCANCODE_DOWN: Key.DOWN,
    sdl2.SDL_SCANCODE_HOME: Key.HOME,
    sdl2.SDL_SCANCODE_END: Key.END,
    sdl2.SDL_SCANCODE_RETURN: Key.ENTER,
    sdl2.SDL_SCANCODE_ESCAPE: Key.ESCAPE,
    sdl2.SDL_SCANCODE_TAB: Key.TAB,
    sdl2.SDL_SCANCODE_SPACE: Key.SPACE,
}

_CONTOUR_POINT_HIT_RADIUS_PX = 14.0


@dataclass
class ContourPointDrag:
    contour_id: str
    point_index: int


class CadApp:
    def __init__(self) -> None:
        self.ui: UI | None = None
        self.controller = CsgEditorController()
        self.camera = OrbitCamera()
        self.viewport = CadViewportWidget(self.camera)
        self.current_path: Path | None = None
        self.last_directory = Path.cwd()
        self.show_wireframe = True
        self._contour_point_drag: ContourPointDrag | None = None

        self.mode_label = Label()
        self.file_label = Label()
        self.summary_label = Label()
        self.selection_label = Label()
        self.status_label = Label()
        self.wireframe_checkbox = Checkbox()
        self.tree = TreeWidget()
        self.context_actions_panel = Panel()
        self.operation_params_panel = Panel()
        self.operation_params_title = Label()
        self.operation_params_kind = Label()
        self.extrude_vector_inputs: dict[str, SpinBox] = {}
        self.operation_transform_inputs: dict[str, SpinBox] = {}
        self._syncing_operation_params = False
        self.primitive_params_panel = Panel()
        self.primitive_params_title = Label()
        self.primitive_param_inputs: dict[str, SpinBox] = {}
        self.primitive_bool_inputs: dict[str, Checkbox] = {}
        self._syncing_primitive_params = False
        self.plane_params_panel = Panel()
        self.plane_params_title = Label()
        self.plane_inputs: dict[str, SpinBox] = {}
        self._syncing_plane_params = False
        self.contour_params_panel = Panel()
        self.contour_point_inputs: dict[tuple[int, str], SpinBox] = {}
        self._syncing_contour_params = False
        self.dirty = True
        self.preview_revision = 0

    @property
    def document(self) -> ProceduralMeshDocument:
        return self.controller.document

    @document.setter
    def document(self, value: ProceduralMeshDocument) -> None:
        self.controller.document = value

    @property
    def draft(self) -> SketchDraft:
        return self.controller.draft

    @draft.setter
    def draft(self, value: SketchDraft) -> None:
        self.controller.draft = value

    @property
    def selected_node_data(self) -> tuple[str, str] | None:
        return self.controller.selection

    @selected_node_data.setter
    def selected_node_data(self, value: tuple[str, str] | None) -> None:
        self.controller.selection = value

    @property
    def mode(self) -> str:
        return self.controller.mode

    @mode.setter
    def mode(self, value: str) -> None:
        self.controller.mode = str(value)

    def build_ui(self, ui: UI):
        self.ui = ui

        root = VStack()
        root.spacing = 0

        menu_bar = self._build_menu_bar()
        root.add_child(menu_bar)

        content = HStack()
        content.spacing = 0
        content.stretch = True

        self.viewport.stretch = True
        self.viewport.on_changed = self.request_render
        self.viewport.on_scene_mouse_down = self._on_scene_mouse_down
        self.viewport.on_scene_mouse_move = self._on_scene_mouse_move
        self.viewport.on_scene_mouse_up = self._on_scene_mouse_up
        self.viewport.on_scene_click = self._on_scene_click

        tree_panel = Panel()
        tree_panel.preferred_width = px(320)
        tree_panel.padding = 10
        tree_panel.background_color = (0.12, 0.125, 0.14, 1.0)
        tree_panel.add_child(self._build_tree_panel())

        side = Panel()
        side.preferred_width = px(340)
        side.padding = 10
        side.background_color = (0.14, 0.145, 0.16, 1.0)
        side.add_child(self._build_side_panel())

        content.add_child(tree_panel)
        content.add_child(Splitter(tree_panel, "right"))
        content.add_child(self.viewport)
        content.add_child(Splitter(side, "left"))
        content.add_child(side)
        root.add_child(content)

        menu_bar.register_shortcuts(ui)
        self.refresh_tree()
        return root

    def _build_menu_bar(self) -> MenuBar:
        menu_bar = MenuBar()

        file_menu = Menu()
        file_menu.items = [
            MenuItem("New", shortcut="Ctrl+N", on_click=self.new_document),
            MenuItem("Open...", shortcut="Ctrl+O", on_click=self.open_state_dialog),
            MenuItem.sep(),
            MenuItem("Save", shortcut="Ctrl+S", on_click=self.save_state),
            MenuItem("Save As...", shortcut="Ctrl+Shift+S", on_click=self.save_state_as_dialog),
        ]
        menu_bar.add_menu("File", file_menu)
        return menu_bar

    def render_scene(self, renderer: CsgSceneRenderer) -> None:
        width = max(int(self.viewport.width), 1)
        height = max(int(self.viewport.height), 1)
        texture = renderer.render_document(
            self.document,
            self.camera,
            width,
            height,
            self.draft.points,
            self.selected_node_data,
            self.show_wireframe,
            (self.preview_revision, self.show_wireframe),
        )
        self.viewport.texture = texture
        self.viewport.texture_size = (width, height)
        self.dirty = False

    def request_render(self) -> None:
        self.dirty = True

    def request_preview_rebuild(self) -> None:
        self.preview_revision += 1
        self.request_render()

    def _on_wireframe_changed(self, checked: bool) -> None:
        self.show_wireframe = bool(checked)
        self.request_preview_rebuild()
        log.info(f"[CsgCad] wireframe visible={self.show_wireframe}")

    def _build_side_panel(self):
        root = VStack()
        root.spacing = 6

        title = Label()
        title.text = "CSG CAD"
        root.add_child(title)

        self.file_label.color = (0.58, 0.64, 0.72, 1.0)
        root.add_child(self.file_label)

        self.mode_label.text = self._mode_text()
        self.mode_label.color = (0.58, 0.64, 0.72, 1.0)
        root.add_child(self.mode_label)

        row = HStack()
        row.spacing = 4
        row.preferred_height = px(28)
        row.add_child(self._button("Draw Sketch", self.start_draw_sketch))
        row.add_child(self._button("Close Contour", self.close_contour))
        root.add_child(row)

        row2 = HStack()
        row2.spacing = 4
        row2.preferred_height = px(28)
        row2.add_child(self._button("Fit", self.fit_camera))
        row2.add_child(self._button("Clear", self.clear_document))
        root.add_child(row2)

        row3 = HStack()
        row3.spacing = 4
        row3.preferred_height = px(28)
        row3.add_child(self._button("Union", lambda: self.add_boolean_operation("union")))
        row3.add_child(self._button("Subtract", lambda: self.add_boolean_operation("subtract")))
        row3.add_child(self._button("Intersect", lambda: self.add_boolean_operation("intersect")))
        root.add_child(row3)

        primitive_row = HStack()
        primitive_row.spacing = 4
        primitive_row.preferred_height = px(28)
        primitive_row.add_child(self._button("Box", lambda: self.add_primitive("box")))
        primitive_row.add_child(self._button("Sphere", lambda: self.add_primitive("sphere")))
        primitive_row.add_child(self._button("Cylinder", lambda: self.add_primitive("cylinder")))
        primitive_row.add_child(self._button("Cone", lambda: self.add_primitive("cone")))
        root.add_child(primitive_row)

        view_row = HStack()
        view_row.spacing = 4
        view_row.preferred_height = px(24)
        self.wireframe_checkbox.text = "Wireframe"
        self.wireframe_checkbox.checked = self.show_wireframe
        self.wireframe_checkbox.on_changed = self._on_wireframe_changed
        view_row.add_child(self.wireframe_checkbox)
        root.add_child(view_row)

        self.summary_label.color = (0.58, 0.64, 0.72, 1.0)
        root.add_child(self.summary_label)

        self.selection_label.color = (0.58, 0.64, 0.72, 1.0)
        root.add_child(self.selection_label)

        self.status_label.text = "Ready"
        self.status_label.color = (0.58, 0.64, 0.72, 1.0)
        root.add_child(self.status_label)

        root.add_child(self._build_context_actions_panel())
        root.add_child(self._build_operation_params_panel())
        root.add_child(self._build_primitive_params_panel())
        root.add_child(self._build_plane_params_panel())
        root.add_child(self._build_contour_params_panel())

        return root

    def _build_tree_panel(self):
        root = VStack()
        root.spacing = 6

        title = Label()
        title.text = "Document Tree"
        root.add_child(title)

        self.tree.row_height = 22
        self.tree.indent_size = 22
        self.tree.stretch = True
        self.tree.draggable = True
        self.tree.on_select = self._on_tree_select
        self.tree.on_drop = self._on_tree_drop
        root.add_child(self.tree)
        return root

    def _button(self, text: str, callback) -> Button:
        button = Button()
        button.text = text
        button.on_click = callback
        return button

    def _build_operation_params_panel(self) -> Panel:
        for child in self.operation_params_panel.children[:]:
            self.operation_params_panel.remove_child(child)
        self.extrude_vector_inputs.clear()
        self.operation_transform_inputs.clear()

        self.operation_params_panel.padding = 8
        self.operation_params_panel.background_color = (0.10, 0.105, 0.12, 1.0)
        self.operation_params_panel.visible = False
        return self.operation_params_panel

    def _rebuild_operation_params_panel(self, operation) -> bool:
        for child in self.operation_params_panel.children[:]:
            self.operation_params_panel.remove_child(child)
        self.extrude_vector_inputs.clear()
        self.operation_transform_inputs.clear()

        body = VStack()
        body.spacing = 5

        self.operation_params_title.text = operation.name
        self.operation_params_title.color = (0.84, 0.88, 0.94, 1.0)
        body.add_child(self.operation_params_title)

        self.operation_params_kind.text = f"Kind: {operation.kind}"
        self.operation_params_kind.color = (0.58, 0.64, 0.72, 1.0)
        body.add_child(self.operation_params_kind)

        separator = Separator()
        separator.orientation = "horizontal"
        body.add_child(separator)

        self._syncing_operation_params = True
        if operation.kind == "extrude":
            source_sketch_id = str(operation.params.get("source_sketch_id", ""))
            sketch = self.document.find_sketch(source_sketch_id)
            if sketch is None:
                self._syncing_operation_params = False
                log.error(
                    "[CsgCad] cannot show extrude parameters: "
                    f"source sketch not found '{source_sketch_id}'"
                )
                return False
            vector = extrude_vector_for_operation(sketch, operation)
            vector_label = Label()
            vector_label.text = "Extrude vector"
            vector_label.color = (0.70, 0.74, 0.80, 1.0)
            body.add_child(vector_label)
            for axis in ("x", "y", "z"):
                row = self._build_vector_row(axis)
                self.extrude_vector_inputs[axis].value = vector[("x", "y", "z").index(axis)]
                body.add_child(row)

        self._append_operation_transform_rows(body, "center", "Center", operation.params)
        self._append_operation_transform_rows(body, "rotation", "Rotation", operation.params)
        self._syncing_operation_params = False

        self.operation_params_panel.add_child(body)
        return True

    def _build_context_actions_panel(self) -> Panel:
        for child in self.context_actions_panel.children[:]:
            self.context_actions_panel.remove_child(child)

        self.context_actions_panel.padding = 8
        self.context_actions_panel.background_color = (0.10, 0.105, 0.12, 1.0)
        self.context_actions_panel.visible = False
        return self.context_actions_panel

    def _rebuild_context_actions_panel(self) -> None:
        for child in self.context_actions_panel.children[:]:
            self.context_actions_panel.remove_child(child)

        actions = self._context_actions()
        if not actions:
            self._set_context_actions_visible(False)
            return

        body = VStack()
        body.spacing = 5

        title = Label()
        title.text = "Actions"
        title.color = (0.84, 0.88, 0.94, 1.0)
        body.add_child(title)

        for label, callback in actions:
            row = HStack()
            row.spacing = 4
            row.preferred_height = px(28)
            row.add_child(self._button(label, callback))
            body.add_child(row)

        self.context_actions_panel.add_child(body)
        self._set_context_actions_visible(True)

    def _context_actions(self):
        if self.selected_node_data is None:
            return []
        kind, item_id = self.selected_node_data
        if kind == "sketch":
            if self.document.find_sketch(item_id) is None:
                return []
            return [
                ("Add Outer Contour", self.start_add_outer_contour),
                ("Extrude Sketch", self.extrude_selected),
            ]
        if kind == "contour":
            contour_ref = self._contour_ref_by_id(item_id)
            if contour_ref is None:
                return []
            _sketch, contour = contour_ref
            if contour.role == CONTOUR_ROLE_OUTER:
                return [("Add Hole", self.start_add_hole_contour)]
        return []

    def _build_vector_row(self, axis: str) -> HStack:
        row = HStack()
        row.spacing = 6
        row.preferred_height = px(26)

        label = Label()
        label.text = axis.upper()
        label.color = (0.58, 0.64, 0.72, 1.0)
        label.preferred_width = px(18)
        row.add_child(label)

        spin = SpinBox()
        spin.decimals = 3
        spin.step = 0.1
        spin.min_value = -1000000.0
        spin.max_value = 1000000.0
        spin.preferred_height = px(24)
        spin.stretch = True
        spin.on_changed = self._on_extrude_vector_changed
        self.extrude_vector_inputs[axis] = spin
        row.add_child(spin)
        return row

    def _append_operation_transform_rows(self, body: VStack, group: str, label_text: str, params: dict) -> None:
        label = Label()
        label.text = label_text
        label.color = (0.70, 0.74, 0.80, 1.0)
        body.add_child(label)
        value = _param_vec3(params, group, (0.0, 0.0, 0.0))
        for index, axis in enumerate(("x", "y", "z")):
            key = f"{group}.{axis}"
            row = HStack()
            row.spacing = 6
            row.preferred_height = px(26)

            axis_label = Label()
            axis_label.text = axis.upper()
            axis_label.color = (0.58, 0.64, 0.72, 1.0)
            axis_label.preferred_width = px(18)
            row.add_child(axis_label)

            spin = SpinBox()
            spin.decimals = 3
            spin.step = 0.1
            spin.min_value = -1000000.0
            spin.max_value = 1000000.0
            spin.preferred_height = px(24)
            spin.stretch = True
            spin.value = value[index]
            spin.on_changed = self._on_operation_transform_changed
            self.operation_transform_inputs[key] = spin
            row.add_child(spin)
            body.add_child(row)

    def _build_primitive_params_panel(self) -> Panel:
        for child in self.primitive_params_panel.children[:]:
            self.primitive_params_panel.remove_child(child)
        self.primitive_param_inputs.clear()
        self.primitive_bool_inputs.clear()

        self.primitive_params_panel.padding = 8
        self.primitive_params_panel.background_color = (0.10, 0.105, 0.12, 1.0)
        self.primitive_params_panel.visible = False
        return self.primitive_params_panel

    def _rebuild_primitive_params_panel(self, operation) -> None:
        for child in self.primitive_params_panel.children[:]:
            self.primitive_params_panel.remove_child(child)
        self.primitive_param_inputs.clear()
        self.primitive_bool_inputs.clear()

        body = VStack()
        body.spacing = 5

        primitive_kind = str(operation.params.get("primitive_kind", ""))
        self.primitive_params_title.text = f"{_primitive_kind_label(primitive_kind)}: {operation.name}"
        self.primitive_params_title.color = (0.84, 0.88, 0.94, 1.0)
        body.add_child(self.primitive_params_title)

        separator = Separator()
        separator.orientation = "horizontal"
        body.add_child(separator)

        self._syncing_primitive_params = True
        self._append_primitive_kind_rows(body, primitive_kind, operation.params)
        self._append_primitive_vector_rows(body, "center", "Center", operation.params, (0.0, 0.0, 0.0))
        self._append_primitive_vector_rows(body, "rotation", "Rotation", operation.params, (0.0, 0.0, 0.0))
        self._syncing_primitive_params = False

        self.primitive_params_panel.add_child(body)

    def _append_primitive_kind_rows(self, body: VStack, primitive_kind: str, params: dict) -> None:
        if primitive_kind == "box":
            self._append_primitive_vector_rows(body, "size", "Size", params, (1.0, 1.0, 1.0), min_value=0.001)
            self._append_primitive_bool_row(body, "centered", "Centered", params, True)
            return
        if primitive_kind == "sphere":
            body.add_child(self._build_primitive_number_row("radius", "Radius", params, 0.5, min_value=0.001))
            body.add_child(
                self._build_primitive_number_row(
                    "circular_segments",
                    "Segments",
                    params,
                    32.0,
                    decimals=0,
                    step=1.0,
                    min_value=3.0,
                    max_value=256.0,
                )
            )
            return
        if primitive_kind == "cylinder":
            body.add_child(self._build_primitive_number_row("radius", "Radius", params, 0.5, min_value=0.001))
            body.add_child(self._build_primitive_number_row("height", "Height", params, 1.0, min_value=0.001))
            body.add_child(
                self._build_primitive_number_row(
                    "circular_segments",
                    "Segments",
                    params,
                    32.0,
                    decimals=0,
                    step=1.0,
                    min_value=3.0,
                    max_value=256.0,
                )
            )
            self._append_primitive_bool_row(body, "centered", "Centered", params, True)
            return
        if primitive_kind == "cone":
            body.add_child(self._build_primitive_number_row("radius_low", "Radius low", params, 0.5, min_value=0.001))
            body.add_child(self._build_primitive_number_row("radius_high", "Radius high", params, 0.0, min_value=0.0))
            body.add_child(self._build_primitive_number_row("height", "Height", params, 1.0, min_value=0.001))
            body.add_child(
                self._build_primitive_number_row(
                    "circular_segments",
                    "Segments",
                    params,
                    32.0,
                    decimals=0,
                    step=1.0,
                    min_value=3.0,
                    max_value=256.0,
                )
            )
            self._append_primitive_bool_row(body, "centered", "Centered", params, True)

    def _append_primitive_vector_rows(
        self,
        body: VStack,
        group: str,
        label_text: str,
        params: dict,
        default: tuple[float, float, float],
        min_value: float = -1000000.0,
    ) -> None:
        label = Label()
        label.text = label_text
        label.color = (0.70, 0.74, 0.80, 1.0)
        body.add_child(label)
        value = _param_vec3(params, group, default)
        for index, axis in enumerate(("x", "y", "z")):
            key = f"{group}.{axis}"
            row = self._build_primitive_number_row(
                key,
                axis.upper(),
                {},
                value[index],
                min_value=min_value,
                label_width=18,
            )
            body.add_child(row)

    def _build_primitive_number_row(
        self,
        key: str,
        label_text: str,
        params: dict,
        default: float,
        decimals: int = 3,
        step: float = 0.1,
        min_value: float = -1000000.0,
        max_value: float = 1000000.0,
        label_width: int = 82,
    ) -> HStack:
        row = HStack()
        row.spacing = 6
        row.preferred_height = px(26)

        label = Label()
        label.text = label_text
        label.color = (0.58, 0.64, 0.72, 1.0)
        label.preferred_width = px(label_width)
        row.add_child(label)

        spin = SpinBox()
        spin.decimals = decimals
        spin.step = step
        spin.min_value = min_value
        spin.max_value = max_value
        spin.preferred_height = px(24)
        spin.stretch = True
        spin.value = float(params.get(key, default))
        spin.on_changed = self._on_primitive_param_changed
        self.primitive_param_inputs[key] = spin
        row.add_child(spin)
        return row

    def _append_primitive_bool_row(self, body: VStack, key: str, label_text: str, params: dict, default: bool) -> None:
        row = HStack()
        row.spacing = 4
        row.preferred_height = px(24)
        checkbox = Checkbox()
        checkbox.text = label_text
        checkbox.checked = bool(params.get(key, default))
        checkbox.on_changed = self._on_primitive_bool_changed
        self.primitive_bool_inputs[key] = checkbox
        row.add_child(checkbox)
        body.add_child(row)

    def _build_plane_params_panel(self) -> Panel:
        for child in self.plane_params_panel.children[:]:
            self.plane_params_panel.remove_child(child)
        self.plane_inputs.clear()

        self.plane_params_panel.padding = 8
        self.plane_params_panel.background_color = (0.10, 0.105, 0.12, 1.0)
        self.plane_params_panel.visible = False

        body = VStack()
        body.spacing = 5

        self.plane_params_title.text = "Plane"
        self.plane_params_title.color = (0.84, 0.88, 0.94, 1.0)
        body.add_child(self.plane_params_title)

        separator = Separator()
        separator.orientation = "horizontal"
        body.add_child(separator)

        for group, label_text in (
            ("origin", "Origin"),
            ("x_axis", "X axis"),
            ("y_axis", "Y axis"),
        ):
            label = Label()
            label.text = label_text
            label.color = (0.70, 0.74, 0.80, 1.0)
            body.add_child(label)
            for axis in ("x", "y", "z"):
                body.add_child(self._build_plane_vector_row(group, axis))

        self.plane_params_panel.add_child(body)
        return self.plane_params_panel

    def _build_plane_vector_row(self, group: str, axis: str) -> HStack:
        row = HStack()
        row.spacing = 6
        row.preferred_height = px(26)

        label = Label()
        label.text = axis.upper()
        label.color = (0.58, 0.64, 0.72, 1.0)
        label.preferred_width = px(18)
        row.add_child(label)

        spin = SpinBox()
        spin.decimals = 3
        spin.step = 0.1
        spin.min_value = -1000000.0
        spin.max_value = 1000000.0
        spin.preferred_height = px(24)
        spin.stretch = True
        spin.on_changed = self._on_plane_param_changed
        self.plane_inputs[f"{group}.{axis}"] = spin
        row.add_child(spin)
        return row

    def _build_contour_params_panel(self) -> Panel:
        for child in self.contour_params_panel.children[:]:
            self.contour_params_panel.remove_child(child)
        self.contour_point_inputs.clear()

        self.contour_params_panel.padding = 8
        self.contour_params_panel.background_color = (0.10, 0.105, 0.12, 1.0)
        self.contour_params_panel.visible = False
        return self.contour_params_panel

    def _rebuild_contour_params_panel(self, contour) -> None:
        for child in self.contour_params_panel.children[:]:
            self.contour_params_panel.remove_child(child)
        self.contour_point_inputs.clear()

        body = VStack()
        body.spacing = 5

        title = Label()
        title.text = f"{_contour_role_label(contour.role)}: {contour.name}"
        title.color = (0.84, 0.88, 0.94, 1.0)
        body.add_child(title)

        role_label = Label()
        role_label.text = self._contour_role_text(contour)
        role_label.color = (0.58, 0.64, 0.72, 1.0)
        body.add_child(role_label)

        hint = Label()
        hint.text = "Local points"
        hint.color = (0.58, 0.64, 0.72, 1.0)
        body.add_child(hint)

        separator = Separator()
        separator.orientation = "horizontal"
        body.add_child(separator)

        self._syncing_contour_params = True
        for index, point in enumerate(contour.points):
            row = self._build_contour_point_row(index)
            self.contour_point_inputs[(index, "x")].value = point[0]
            self.contour_point_inputs[(index, "y")].value = point[1]
            body.add_child(row)
        self._syncing_contour_params = False

        self.contour_params_panel.add_child(body)

    def _build_contour_point_row(self, point_index: int) -> HStack:
        row = HStack()
        row.spacing = 6
        row.preferred_height = px(26)

        label = Label()
        label.text = f"P{point_index}"
        label.color = (0.58, 0.64, 0.72, 1.0)
        label.preferred_width = px(32)
        row.add_child(label)

        for axis in ("x", "y"):
            axis_label = Label()
            axis_label.text = axis.upper()
            axis_label.color = (0.58, 0.64, 0.72, 1.0)
            axis_label.preferred_width = px(14)
            row.add_child(axis_label)

            spin = SpinBox()
            spin.decimals = 3
            spin.step = 0.1
            spin.min_value = -1000000.0
            spin.max_value = 1000000.0
            spin.preferred_height = px(24)
            spin.stretch = True
            spin.on_changed = lambda value, i=point_index, a=axis: self._on_contour_point_changed(i, a, value)
            self.contour_point_inputs[(point_index, axis)] = spin
            row.add_child(spin)
        return row

    def new_document(self) -> None:
        result = self.controller.new_document()
        self.current_path = None
        self._apply_controller_result(result, default_status="New document")
        log.info("[CsgCad] new document")

    def open_state_dialog(self) -> None:
        ui = self.ui
        if ui is None:
            log.error("[CsgCad] cannot open file dialog: UI is not available")
            return
        show_open_file_dialog(
            ui,
            self._on_open_state_path,
            title="Open termin-csg CAD State",
            directory=str(self._file_dialog_directory()),
            filter_str=CAD_STATE_FILTER,
        )

    def save_state(self) -> None:
        if self.current_path is None:
            self.save_state_as_dialog()
            return
        self.save_state_to_path(self.current_path)

    def save_state_as_dialog(self) -> None:
        ui = self.ui
        if ui is None:
            log.error("[CsgCad] cannot open save dialog: UI is not available")
            return
        show_save_file_dialog(
            ui,
            self._on_save_state_path,
            title="Save termin-csg CAD State",
            directory=str(self._file_dialog_directory()),
            filter_str=CAD_STATE_FILTER,
        )

    def save_state_to_path(self, path: str | Path) -> bool:
        try:
            saved_path = save_cad_state(
                path,
                CadState.from_app_state(
                    self.document,
                    self.camera,
                    self.selected_node_data,
                ),
            )
        except Exception as e:
            self._set_status("Save failed")
            log.error(f"[CsgCad] failed to save state path='{path}': {e}")
            return False

        self.current_path = saved_path
        self.last_directory = saved_path.parent
        self._refresh_labels()
        self._set_status(f"Saved: {saved_path.name}")
        log.info(f"[CsgCad] state saved path='{saved_path}'")
        return True

    def load_state_from_path(self, path: str | Path) -> bool:
        try:
            state = load_cad_state(path)
        except Exception as e:
            self._set_status("Open failed")
            log.error(f"[CsgCad] failed to load state path='{path}': {e}")
            return False

        self.controller.replace_document(state.document)
        state.camera.apply_to(self.camera)
        self.selected_node_data = self._validated_selection(state.selection)
        self.current_path = Path(path).expanduser()
        self.last_directory = self.current_path.parent
        self.refresh_tree()
        self.request_preview_rebuild()
        self._set_status(f"Opened: {self.current_path.name}")
        log.info(f"[CsgCad] state loaded path='{self.current_path}'")
        return True

    def _on_open_state_path(self, path: str | None) -> None:
        if path is None:
            self._set_status("Open cancelled")
            return
        self.load_state_from_path(path)

    def _on_save_state_path(self, path: str | None) -> None:
        if path is None:
            self._set_status("Save cancelled")
            return
        self.save_state_to_path(path)

    def start_draw_sketch(self) -> None:
        result = self.controller.start_draw_sketch()
        self._apply_controller_result(result)
        log.info("[CsgCad] mode=draw_sketch")

    def start_add_outer_contour(self) -> None:
        result = self.controller.start_add_outer_contour()
        if not self._apply_controller_result(result):
            return
        log.info(f"[CsgCad] add outer contour started sketch='{self.draft.sketch_id}'")

    def start_add_hole_contour(self) -> None:
        result = self.controller.start_add_hole_contour()
        if not self._apply_controller_result(result):
            return
        log.info(
            "[CsgCad] add hole contour started "
            f"sketch='{self.draft.sketch_id}' outer='{self.draft.parent_contour_id}'"
        )

    def close_contour(self) -> None:
        result = self.controller.close_contour()
        if not self._apply_controller_result(result):
            return
        log.info(f"[CsgCad] contour closed selection='{self.selected_node_data}'")

    def extrude_selected(self) -> None:
        previous_selection = self.selected_node_data
        result = self.controller.extrude_selected()
        if not self._apply_controller_result(result):
            return
        log.info(f"[CsgCad] extrude added selection='{self.selected_node_data}' previous='{previous_selection}'")

    def add_boolean_operation(self, kind: str) -> None:
        result = self.controller.add_boolean_operation(kind)
        if not self._apply_controller_result(result):
            return
        log.info(f"[CsgCad] boolean added kind='{kind}' selection='{self.selected_node_data}'")

    def add_primitive(self, kind: str) -> None:
        result = self.controller.add_primitive(kind)
        if not self._apply_controller_result(result, default_status=f"{_primitive_kind_label(kind)} added"):
            return
        log.info(f"[CsgCad] primitive added kind='{kind}' selection='{self.selected_node_data}'")

    def fit_camera(self) -> None:
        lo, hi = document_bounds(self.document)
        self.camera.fit_bounds(lo, hi)
        self.request_render()

    def clear_document(self) -> None:
        result = self.controller.new_document()
        self.current_path = None
        self._apply_controller_result(result, default_status="Cleared")
        log.info("[CsgCad] document cleared")

    def _apply_controller_result(
        self,
        result: CsgEditorCommandResult,
        default_status: str = "",
    ) -> bool:
        if not result.success:
            if result.message:
                self._set_status(result.message)
            return False
        if result.tree_changed:
            self.refresh_tree()
        else:
            self._refresh_labels()
            if result.selection_changed:
                self._rebuild_context_actions_panel()
                self._refresh_operation_params_panel()
                self._refresh_primitive_params_panel()
                self._refresh_plane_params_panel()
                self._refresh_contour_params_panel()
        if result.fit_camera:
            self.fit_camera()
        if result.preview_changed:
            self.request_preview_rebuild()
        status = result.message if result.message else default_status
        if status:
            self._set_status(status)
        return True

    def refresh_tree(self) -> None:
        self.tree.clear()
        roots = build_document_tree(self.document)
        for root in roots:
            self.tree.add_root(self._to_tree_node(root))
        self._restore_tree_selection(self.tree.root_nodes)
        self._refresh_labels()
        self._rebuild_context_actions_panel()
        self._refresh_operation_params_panel()
        self._refresh_primitive_params_panel()
        self._refresh_plane_params_panel()
        self._refresh_contour_params_panel()
        if self.tree._ui is not None:
            self.tree._ui.request_layout()

    def _to_tree_node(self, source: DocumentTreeNode) -> TreeNode:
        label = Label()
        label.text = source.text
        label.color = (0.70, 0.74, 0.80, 1.0)
        node = TreeNode(label)
        node.data = (source.kind, source.item_id)
        node.expanded = True
        for child in source.children:
            node.add_node(self._to_tree_node(child))
        return node

    def _restore_tree_selection(self, roots: list[TreeNode]) -> None:
        for root in roots:
            selected = self._find_tree_node(root, self.selected_node_data)
            if selected is not None:
                self.tree.selected_node = selected
                selected._selected = True
                return

    def _find_tree_node(self, root: TreeNode, data: tuple[str, str] | None) -> TreeNode | None:
        if data is None:
            return None
        if root.data == data:
            return root
        for child in root.subnodes:
            found = self._find_tree_node(child, data)
            if found is not None:
                return found
        return None

    def _on_tree_select(self, node: TreeNode) -> None:
        self.selected_node_data = node.data
        self._refresh_labels()
        self._rebuild_context_actions_panel()
        self._refresh_operation_params_panel()
        self._refresh_primitive_params_panel()
        self._refresh_plane_params_panel()
        self._refresh_contour_params_panel()
        self.request_preview_rebuild()

    def _on_tree_drop(self, dragged_node: TreeNode, target_node: TreeNode | None, position: str) -> None:
        dragged_data = self._tree_node_data(dragged_node)
        if dragged_data is None or dragged_data[0] != "operation":
            log.error("[CsgCad] cannot drop tree node: drag an operation node")
            return
        dragged_operation_id = dragged_data[1]
        if self.document.find_operation(dragged_operation_id) is None:
            log.error(f"[CsgCad] cannot drop tree node: operation not found '{dragged_operation_id}'")
            return

        source_boolean_id = self._boolean_parent_id_for_tree_node(dragged_node)
        if position == "root":
            if not source_boolean_id:
                return
            result = self.controller.remove_boolean_input(source_boolean_id, dragged_operation_id)
            self._finish_tree_drop(result)
            return

        if target_node is None:
            log.error("[CsgCad] cannot drop tree node: missing drop target")
            return

        if position == "inside":
            target_boolean_id = self._boolean_operation_id_for_tree_node(target_node)
            if not target_boolean_id:
                log.error("[CsgCad] cannot drop tree node inside target: target is not a boolean operation")
                return
            if source_boolean_id:
                if source_boolean_id == target_boolean_id:
                    log.error("[CsgCad] cannot drop tree node inside target: input is already in this boolean operation")
                    return
                result = self.controller.move_boolean_input(
                    source_boolean_id,
                    target_boolean_id,
                    dragged_operation_id,
                )
            else:
                result = self.controller.add_boolean_input(target_boolean_id, dragged_operation_id)
            self._finish_tree_drop(result)
            return

        if position not in ("above", "below"):
            log.error(f"[CsgCad] cannot drop tree node: unsupported drop position '{position}'")
            return

        target_boolean_id = self._boolean_parent_id_for_tree_node(target_node)
        if not target_boolean_id:
            log.error("[CsgCad] cannot reorder boolean input: drop above or below an input inside a boolean operation")
            return
        target_data = self._tree_node_data(target_node)
        if target_data is None:
            log.error("[CsgCad] cannot reorder boolean input: target node has no document data")
            return
        target_operation_id = target_data[1]
        target_operation = self.document.find_operation(target_boolean_id)
        if target_operation is None:
            log.error(f"[CsgCad] cannot reorder boolean input: boolean operation not found '{target_boolean_id}'")
            return
        if target_operation_id not in target_operation.inputs:
            log.error(
                "[CsgCad] cannot reorder boolean input: "
                f"target input not found operation='{target_boolean_id}' input='{target_operation_id}'"
            )
            return
        target_index = target_operation.inputs.index(target_operation_id)
        insert_index = target_index + (1 if position == "below" else 0)
        if source_boolean_id:
            result = self.controller.move_boolean_input(
                source_boolean_id,
                target_boolean_id,
                dragged_operation_id,
                insert_index,
            )
        else:
            result = self.controller.add_boolean_input(target_boolean_id, dragged_operation_id, insert_index)
        self._finish_tree_drop(result)

    def _finish_tree_drop(self, result: CsgEditorCommandResult) -> None:
        if not self._apply_controller_result(result):
            return
        log.info(f"[CsgCad] tree drop applied selection='{self.selected_node_data}' status='{result.message}'")

    def _tree_node_data(self, node: TreeNode | None) -> tuple[str, str] | None:
        if node is None:
            return None
        data = node.data
        if not isinstance(data, tuple) or len(data) != 2:
            return None
        return (str(data[0]), str(data[1]))

    def _boolean_operation_id_for_tree_node(self, node: TreeNode | None) -> str:
        data = self._tree_node_data(node)
        if data is None or data[0] != "operation":
            return ""
        operation = self.document.find_operation(data[1])
        if operation is None or operation.kind not in BOOLEAN_OPERATION_KINDS:
            return ""
        return operation.id

    def _boolean_parent_id_for_tree_node(self, node: TreeNode | None) -> str:
        if node is None:
            return ""
        data = self._tree_node_data(node)
        if data is None:
            return ""
        parent = self.tree._find_parent(node)
        parent_boolean_id = self._boolean_operation_id_for_tree_node(parent)
        if not parent_boolean_id:
            return ""
        parent_operation = self.document.find_operation(parent_boolean_id)
        if parent_operation is None:
            return ""
        if data[1] not in parent_operation.inputs:
            return ""
        return parent_operation.id

    def _on_scene_mouse_down(self, x: float, y: float, width: int, height: int) -> bool:
        drag = self._pick_selected_contour_point(x, y, width, height)
        if drag is None:
            return False
        self._contour_point_drag = drag
        self._set_status(f"Dragging contour point P{drag.point_index}")
        log.info(
            "[CsgCad] contour point drag started "
            f"contour='{drag.contour_id}' index={drag.point_index}"
        )
        return True

    def _on_scene_mouse_move(self, x: float, y: float, width: int, height: int) -> bool:
        if self._contour_point_drag is None:
            return False
        return self._drag_contour_point_to_screen(x, y, width, height)

    def _on_scene_mouse_up(self, x: float, y: float, width: int, height: int) -> bool:
        drag = self._contour_point_drag
        if drag is None:
            return False
        self._drag_contour_point_to_screen(x, y, width, height)
        self._contour_point_drag = None
        self._set_status(f"Contour point P{drag.point_index} moved")
        log.info(
            "[CsgCad] contour point drag finished "
            f"contour='{drag.contour_id}' index={drag.point_index}"
        )
        return True

    def _on_scene_click(self, x: float, y: float, width: int, height: int) -> bool:
        if self.mode != "draw_sketch":
            return False
        ray_origin, ray_direction = self.camera.screen_ray(x, y, width, height)
        fallback_point = self.camera.world_point_on_z_plane(x, y, width, height, 0.0)
        result = self.controller.add_draft_point_from_ray(
            ray_origin,
            ray_direction,
            fallback_point=fallback_point,
            fallback_plane=ProceduralPlane(),
            fallback_kind="oxy",
        )
        if not self._apply_controller_result(result):
            return True
        if not self.draft.points:
            log.error("[CsgCad] cannot add draft point: controller did not append a point")
            return True
        point = self.draft.points[-1]
        log.info(
            "[CsgCad] draft point added "
            f"point=({point[0]:.3f}, {point[1]:.3f}, {point[2]:.3f}) "
            f"count={len(self.draft.points)}"
        )
        return True

    def _pick_selected_contour_point(
        self,
        x: float,
        y: float,
        width: int,
        height: int,
    ) -> ContourPointDrag | None:
        contour_ref = self._selected_contour_ref()
        if contour_ref is None:
            return None
        sketch, contour = contour_ref
        best_index = -1
        best_distance_sq = _CONTOUR_POINT_HIT_RADIUS_PX * _CONTOUR_POINT_HIT_RADIUS_PX
        for index, point in enumerate(sketch.contour_points(contour)):
            screen_point = self._project_world_to_screen(point, width, height)
            if screen_point is None:
                continue
            dx = screen_point[0] - float(x)
            dy = screen_point[1] - float(y)
            distance_sq = dx * dx + dy * dy
            if distance_sq <= best_distance_sq:
                best_distance_sq = distance_sq
                best_index = index
        if best_index < 0:
            return None
        return ContourPointDrag(contour.id, best_index)

    def _drag_contour_point_to_screen(self, x: float, y: float, width: int, height: int) -> bool:
        drag = self._contour_point_drag
        if drag is None:
            return False
        contour_ref = self._contour_ref_by_id(drag.contour_id)
        if contour_ref is None:
            log.error(f"[CsgCad] cannot drag contour point: contour not found '{drag.contour_id}'")
            self._contour_point_drag = None
            return True
        sketch, contour = contour_ref
        ray_origin, ray_direction = self.camera.screen_ray(x, y, width, height)
        point = ray_plane_intersection(ray_origin, ray_direction, sketch.plane)
        if point is None:
            log.error(
                "[CsgCad] cannot drag contour point: "
                f"ray does not hit sketch plane contour='{contour.id}' index={drag.point_index}"
            )
            return True
        local_point = sketch.plane.project(point)
        result = self.controller.set_contour_point(contour.id, drag.point_index, local_point)
        if not result.success:
            return True
        self._sync_contour_point_inputs(drag.point_index, local_point)
        self.request_preview_rebuild()
        return True

    def _project_world_to_screen(
        self,
        point: tuple[float, float, float],
        width: int,
        height: int,
    ) -> tuple[float, float] | None:
        mvp = self.camera.view_projection(width, height)
        clip = mvp @ np.array((point[0], point[1], point[2], 1.0), dtype=np.float32)
        w = float(clip[3])
        if w <= 1.0e-8:
            return None
        ndc = clip[:3] / w
        return (
            float((ndc[0] + 1.0) * 0.5 * float(width)),
            float((ndc[1] + 1.0) * 0.5 * float(height)),
        )

    def _refresh_labels(self) -> None:
        if self.current_path is None:
            self.file_label.text = "File: <unsaved>"
        else:
            self.file_label.text = f"File: {self.current_path.name}"
        self.mode_label.text = self._mode_text()
        self.summary_label.text = document_summary(self.document)
        if self.selected_node_data is None:
            self.selection_label.text = "Selection: <none>"
        else:
            self.selection_label.text = (
                f"Selection: {self.selected_node_data[0]} "
                f"{self.selected_node_data[1][:10]}"
            )

    def _refresh_operation_params_panel(self) -> None:
        operation = self._selected_operation()
        if operation is None:
            self._set_operation_params_visible(False)
            return
        if operation.kind == PRIMITIVE_OPERATION_KIND:
            self._set_operation_params_visible(False)
            return
        if operation.kind != "extrude" and operation.kind not in BOOLEAN_OPERATION_KINDS:
            self._set_operation_params_visible(False)
            return
        if not self._rebuild_operation_params_panel(operation):
            self._set_operation_params_visible(False)
            return
        self._set_operation_params_visible(True)

    def _refresh_primitive_params_panel(self) -> None:
        operation = self._selected_primitive_operation()
        if operation is None:
            self._set_primitive_params_visible(False)
            return
        self._rebuild_primitive_params_panel(operation)
        self._set_primitive_params_visible(True)

    def _refresh_plane_params_panel(self) -> None:
        sketch = self._selected_plane_sketch()
        if sketch is None:
            self._set_plane_params_visible(False)
            return

        self.plane_params_title.text = f"Plane: {sketch.name}"
        self._syncing_plane_params = True
        self._set_plane_input_vec("origin", sketch.plane.origin)
        self._set_plane_input_vec("x_axis", sketch.plane.x_axis)
        self._set_plane_input_vec("y_axis", sketch.plane.y_axis)
        self._syncing_plane_params = False
        self._set_plane_params_visible(True)

    def _refresh_contour_params_panel(self) -> None:
        contour_ref = self._selected_contour_ref()
        if contour_ref is None:
            self._set_contour_params_visible(False)
            return
        _sketch, contour = contour_ref
        self._rebuild_contour_params_panel(contour)
        self._set_contour_params_visible(True)

    def _contour_role_text(self, contour) -> str:
        if contour.role != CONTOUR_ROLE_HOLE:
            return "Role: Outer"
        parent_ref = self._contour_ref_by_id(str(contour.parent_contour_id or ""))
        if parent_ref is None:
            return f"Role: Hole; parent: <missing {contour.parent_contour_id}>"
        _sketch, parent = parent_ref
        return f"Role: Hole; parent: {parent.name}"

    def _set_operation_params_visible(self, visible: bool) -> None:
        if self.operation_params_panel.visible == visible:
            return
        self.operation_params_panel.visible = visible
        if self.ui is not None:
            self.ui.request_layout()

    def _set_primitive_params_visible(self, visible: bool) -> None:
        if self.primitive_params_panel.visible == visible:
            return
        self.primitive_params_panel.visible = visible
        if self.ui is not None:
            self.ui.request_layout()

    def _set_plane_params_visible(self, visible: bool) -> None:
        if self.plane_params_panel.visible == visible:
            return
        self.plane_params_panel.visible = visible
        if self.ui is not None:
            self.ui.request_layout()

    def _set_contour_params_visible(self, visible: bool) -> None:
        if self.contour_params_panel.visible == visible:
            return
        self.contour_params_panel.visible = visible
        if self.ui is not None:
            self.ui.request_layout()

    def _set_context_actions_visible(self, visible: bool) -> None:
        if self.context_actions_panel.visible == visible:
            return
        self.context_actions_panel.visible = visible
        if self.ui is not None:
            self.ui.request_layout()

    def _selected_operation(self):
        if self.selected_node_data is None:
            return None
        kind, item_id = self.selected_node_data
        if kind != "operation":
            return None
        return self.document.find_operation(item_id)

    def _selected_primitive_operation(self):
        operation = self._selected_operation()
        if operation is None or operation.kind != PRIMITIVE_OPERATION_KIND:
            return None
        return operation

    def _selected_sketch(self):
        if self.selected_node_data is None:
            return None
        kind, item_id = self.selected_node_data
        if kind != "sketch":
            return None
        return self.document.find_sketch(item_id)

    def _selected_plane_sketch(self):
        if self.selected_node_data is None:
            return None
        kind, item_id = self.selected_node_data
        if kind != "plane":
            return None
        return self.document.find_sketch(item_id)

    def _selected_contour_ref(self):
        if self.selected_node_data is None:
            return None
        kind, item_id = self.selected_node_data
        if kind != "contour":
            return None
        return self._contour_ref_by_id(item_id)

    def _contour_ref_by_id(self, contour_id: str):
        for sketch in self.document.items:
            for contour in sketch.contours:
                if contour.id == contour_id:
                    return (sketch, contour)
        return None

    def _on_extrude_vector_changed(self, _value: float) -> None:
        if self._syncing_operation_params:
            return
        operation = self._selected_operation()
        if operation is None:
            log.error("[CsgCad] cannot update extrude vector: no operation is selected")
            return
        vector = (
            float(self.extrude_vector_inputs["x"].value),
            float(self.extrude_vector_inputs["y"].value),
            float(self.extrude_vector_inputs["z"].value),
        )
        result = self.controller.set_extrude_vector(operation.id, vector)
        if not self._apply_controller_result(result):
            return
        log.info(
            "[CsgCad] extrude vector changed "
            f"operation='{operation.id}' vector=({vector[0]:.3f}, {vector[1]:.3f}, {vector[2]:.3f})"
        )

    def _on_operation_transform_changed(self, _value: float) -> None:
        if self._syncing_operation_params:
            return
        operation = self._selected_operation()
        if operation is None:
            log.error("[CsgCad] cannot update operation transform: no operation is selected")
            return
        center = self._operation_transform_vec("center")
        rotation = self._operation_transform_vec("rotation")
        result = self.controller.set_operation_transform(operation.id, center, rotation)
        if not self._apply_controller_result(result):
            return
        log.info(
            "[CsgCad] operation transform changed "
            f"operation='{operation.id}' center={center} rotation={rotation}"
        )

    def _on_primitive_param_changed(self, _value: float) -> None:
        if self._syncing_primitive_params:
            return
        self._apply_primitive_params_from_inputs()

    def _on_primitive_bool_changed(self, _checked: bool) -> None:
        if self._syncing_primitive_params:
            return
        self._apply_primitive_params_from_inputs()

    def _apply_primitive_params_from_inputs(self) -> None:
        operation = self._selected_primitive_operation()
        if operation is None:
            log.error("[CsgCad] cannot update primitive params: no primitive operation is selected")
            return
        params: dict = {}
        for key, spin in self.primitive_param_inputs.items():
            if "." in key:
                continue
            value = float(spin.value)
            if key == "circular_segments":
                params[key] = int(round(value))
            else:
                params[key] = value
        for group in ("size", "center", "rotation"):
            x_key = f"{group}.x"
            y_key = f"{group}.y"
            z_key = f"{group}.z"
            if x_key in self.primitive_param_inputs and y_key in self.primitive_param_inputs and z_key in self.primitive_param_inputs:
                params[group] = [
                    float(self.primitive_param_inputs[x_key].value),
                    float(self.primitive_param_inputs[y_key].value),
                    float(self.primitive_param_inputs[z_key].value),
                ]
        for key, checkbox in self.primitive_bool_inputs.items():
            params[key] = bool(checkbox.checked)
        result = self.controller.set_primitive_params(operation.id, params)
        if not self._apply_controller_result(result):
            return
        log.info(f"[CsgCad] primitive params changed operation='{operation.id}' params={params}")

    def _operation_transform_vec(self, group: str) -> tuple[float, float, float]:
        return (
            float(self.operation_transform_inputs[f"{group}.x"].value),
            float(self.operation_transform_inputs[f"{group}.y"].value),
            float(self.operation_transform_inputs[f"{group}.z"].value),
        )

    def _on_plane_param_changed(self, _value: float) -> None:
        if self._syncing_plane_params:
            return
        sketch = self._selected_plane_sketch()
        if sketch is None:
            log.error("[CsgCad] cannot update plane: no plane is selected")
            return
        plane = ProceduralPlane(
            origin=self._plane_input_vec("origin"),
            x_axis=self._plane_input_vec("x_axis"),
            y_axis=self._plane_input_vec("y_axis"),
        )
        result = self.controller.set_sketch_plane(sketch.id, plane)
        if not self._apply_controller_result(result):
            return
        log.info(
            "[CsgCad] plane changed "
            f"sketch='{sketch.id}' origin={plane.origin} x_axis={plane.x_axis} y_axis={plane.y_axis}"
        )

    def _on_contour_point_changed(self, point_index: int, axis: str, _value: float) -> None:
        if self._syncing_contour_params:
            return
        contour_ref = self._selected_contour_ref()
        if contour_ref is None:
            log.error("[CsgCad] cannot update contour point: no contour is selected")
            return
        _sketch, contour = contour_ref
        x_key = (point_index, "x")
        y_key = (point_index, "y")
        if x_key not in self.contour_point_inputs or y_key not in self.contour_point_inputs:
            log.error(
                "[CsgCad] cannot update contour point: "
                f"input widgets are missing contour='{contour.id}' index={point_index} axis='{axis}'"
            )
            return
        point = (
            float(self.contour_point_inputs[x_key].value),
            float(self.contour_point_inputs[y_key].value),
        )
        result = self.controller.set_contour_point(contour.id, point_index, point)
        if not self._apply_controller_result(result):
            return
        log.info(
            "[CsgCad] contour point changed "
            f"contour='{contour.id}' index={point_index} point=({point[0]:.3f}, {point[1]:.3f})"
        )

    def _sync_contour_point_inputs(self, point_index: int, point: tuple[float, float]) -> None:
        x_key = (point_index, "x")
        y_key = (point_index, "y")
        if x_key not in self.contour_point_inputs or y_key not in self.contour_point_inputs:
            return
        self._syncing_contour_params = True
        try:
            self.contour_point_inputs[x_key].value = point[0]
            self.contour_point_inputs[y_key].value = point[1]
        finally:
            self._syncing_contour_params = False

    def _set_plane_input_vec(self, group: str, value: tuple[float, float, float]) -> None:
        self.plane_inputs[f"{group}.x"].value = value[0]
        self.plane_inputs[f"{group}.y"].value = value[1]
        self.plane_inputs[f"{group}.z"].value = value[2]

    def _plane_input_vec(self, group: str) -> tuple[float, float, float]:
        return (
            float(self.plane_inputs[f"{group}.x"].value),
            float(self.plane_inputs[f"{group}.y"].value),
            float(self.plane_inputs[f"{group}.z"].value),
        )

    def _mode_text(self) -> str:
        return f"Mode: {self.mode}; draft points: {len(self.draft.points)}"

    def _set_status(self, text: str) -> None:
        self.status_label.text = f"Status: {text}"

    def _file_dialog_directory(self) -> Path:
        if self.current_path is not None:
            return self.current_path.parent
        return self.last_directory

    def _validated_selection(self, selection: tuple[str, str] | None) -> tuple[str, str] | None:
        if selection is None:
            return None
        kind, item_id = selection
        if kind == "sketch" and self.document.find_sketch(item_id) is not None:
            return selection
        if kind == "operation" and self.document.find_operation(item_id) is not None:
            return selection
        if kind == "plane" and self.document.find_sketch(item_id) is not None:
            return selection
        if kind == "contour":
            for item in self.document.items:
                for contour in item.contours:
                    if contour.id == item_id:
                        return selection
        log.error(f"[CsgCad] saved selection is missing kind='{kind}' id='{item_id}'")
        return None


def run_cad_app(title: str = "termin-csg CAD", size: tuple[int, int] = (1200, 760)) -> None:
    window = SDLBackendWindow(title, int(size[0]), int(size[1]))
    window.maximize()
    graphics = Tgfx2Context.from_window(window.device_ptr(), window.context_ptr())
    ui = UI(graphics=graphics)
    app = CadApp()
    ui.root = app.build_ui(ui)
    scene_renderer = CsgSceneRenderer(graphics)

    sdl2.SDL_StartTextInput()
    event = sdl2.SDL_Event()
    try:
        while not window.should_close():
            if sdl2.SDL_WaitEventTimeout(ctypes.byref(event), 16):
                _dispatch_event(window, ui, event)
                while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
                    _dispatch_event(window, ui, event)

            width, height = window.framebuffer_size()
            if width <= 0 or height <= 0:
                continue
            if app.dirty:
                app.render_scene(scene_renderer)
            texture = ui.render_compose(width, height, background_color=(0.10, 0.10, 0.12, 1.0))
            ui.process_deferred()
            if texture is not None:
                window.present(texture)
    finally:
        scene_renderer.close()
        window.close()
        sdl2.SDL_Quit()


def _dispatch_event(window, ui: UI, ev) -> None:
    event_type = ev.type
    if event_type == sdl2.SDL_QUIT:
        window.set_should_close(True)
    elif event_type == sdl2.SDL_KEYDOWN:
        key = _translate_key(ev.key.keysym.scancode)
        mods = _translate_mods(sdl2.SDL_GetModState())
        if ui.key_down(key, mods):
            return
        if key == Key.ESCAPE:
            window.set_should_close(True)
    elif event_type == sdl2.SDL_TEXTINPUT:
        ui.text_input(ev.text.text.decode("utf-8"))
    elif event_type == sdl2.SDL_WINDOWEVENT:
        if ev.window.event == sdl2.SDL_WINDOWEVENT_CLOSE:
            window.set_should_close(True)
    elif event_type == sdl2.SDL_MOUSEMOTION:
        ui.mouse_move(float(ev.motion.x), float(ev.motion.y))
    elif event_type == sdl2.SDL_MOUSEBUTTONDOWN:
        ui.mouse_down(
            float(ev.button.x),
            float(ev.button.y),
            _SDL_BUTTON_MAP.get(ev.button.button, MouseButton.LEFT),
            _translate_mods(sdl2.SDL_GetModState()),
        )
    elif event_type == sdl2.SDL_MOUSEBUTTONUP:
        ui.mouse_up(
            float(ev.button.x),
            float(ev.button.y),
            _SDL_BUTTON_MAP.get(ev.button.button, MouseButton.LEFT),
            _translate_mods(sdl2.SDL_GetModState()),
        )
    elif event_type == sdl2.SDL_MOUSEWHEEL:
        mx, my = ctypes.c_int(), ctypes.c_int()
        sdl2.SDL_GetMouseState(ctypes.byref(mx), ctypes.byref(my))
        ui.mouse_wheel(
            float(ev.wheel.x),
            float(ev.wheel.y),
            float(mx.value),
            float(my.value),
            _translate_mods(sdl2.SDL_GetModState()),
        )


def _translate_key(scancode: int) -> Key:
    if scancode in _KEY_MAP:
        return _KEY_MAP[scancode]
    keycode = sdl2.SDL_GetKeyFromScancode(scancode)
    if ord("a") <= keycode <= ord("z"):
        keycode -= 32
    if 0 <= keycode < 128:
        try:
            return Key(keycode)
        except ValueError:
            return Key.UNKNOWN
    return Key.UNKNOWN


def _contour_role_label(role: str) -> str:
    if role == CONTOUR_ROLE_HOLE:
        return "Hole"
    return "Outer"


def _primitive_kind_label(kind: str) -> str:
    if kind == "box":
        return "Box"
    if kind == "sphere":
        return "Sphere"
    if kind == "cylinder":
        return "Cylinder"
    if kind == "cone":
        return "Cone"
    return "Primitive"


def _param_vec3(params: dict, key: str, default: tuple[float, float, float]) -> tuple[float, float, float]:
    value = params.get(key, default)
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except Exception:
        return default


def _translate_mods(sdl_mods: int) -> int:
    result = 0
    if sdl_mods & (sdl2.KMOD_LSHIFT | sdl2.KMOD_RSHIFT):
        result |= Mods.SHIFT.value
    if sdl_mods & (sdl2.KMOD_LCTRL | sdl2.KMOD_RCTRL):
        result |= Mods.CTRL.value
    if sdl_mods & (sdl2.KMOD_LALT | sdl2.KMOD_RALT):
        result |= Mods.ALT.value
    return result


__all__ = [
    "CadApp",
    "run_cad_app",
]
