"""Standalone mini CAD application for procedural CSG documents."""

from __future__ import annotations

import ctypes
from pathlib import Path

import sdl2

from tcbase import Key, Mods, MouseButton, log
from tcgui.widgets.button import Button
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
from termin.csg.document_edit import (
    SketchDraft,
    add_boolean_for_selection,
    add_draft_point_from_ray,
    add_extrude_for_selection,
    clear_document,
    close_draft_contour,
    selected_sketch_id,
    set_contour_point,
    set_extrude_vector,
    set_sketch_plane,
    start_sketch_draft,
)
from termin.csg.document_eval import extrude_vector_for_operation
from termin.csg.document_tree_model import DocumentTreeNode, build_document_tree, document_summary
from termin.csg.procedural_document import ProceduralMeshDocument, ProceduralPlane
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


class CadApp:
    def __init__(self) -> None:
        self.ui: UI | None = None
        self.document = ProceduralMeshDocument()
        self.camera = OrbitCamera()
        self.viewport = CadViewportWidget(self.camera)
        self.mode = "idle"
        self.draft: SketchDraft = start_sketch_draft()
        self.selected_node_data: tuple[str, str] | None = None
        self.current_path: Path | None = None
        self.last_directory = Path.cwd()

        self.mode_label = Label()
        self.file_label = Label()
        self.summary_label = Label()
        self.selection_label = Label()
        self.status_label = Label()
        self.tree = TreeWidget()
        self.operation_params_panel = Panel()
        self.operation_params_title = Label()
        self.operation_params_kind = Label()
        self.extrude_vector_inputs: dict[str, SpinBox] = {}
        self._syncing_operation_params = False
        self.plane_params_panel = Panel()
        self.plane_params_title = Label()
        self.plane_inputs: dict[str, SpinBox] = {}
        self._syncing_plane_params = False
        self.contour_params_panel = Panel()
        self.contour_point_inputs: dict[tuple[int, str], SpinBox] = {}
        self._syncing_contour_params = False
        self.dirty = True
        self.preview_revision = 0

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
            self.preview_revision,
        )
        self.viewport.texture = texture
        self.viewport.texture_size = (width, height)
        self.dirty = False

    def request_render(self) -> None:
        self.dirty = True

    def request_preview_rebuild(self) -> None:
        self.preview_revision += 1
        self.request_render()

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
        row2.add_child(self._button("Extrude", self.extrude_selected))
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

        self.summary_label.color = (0.58, 0.64, 0.72, 1.0)
        root.add_child(self.summary_label)

        self.selection_label.color = (0.58, 0.64, 0.72, 1.0)
        root.add_child(self.selection_label)

        self.status_label.text = "Ready"
        self.status_label.color = (0.58, 0.64, 0.72, 1.0)
        root.add_child(self.status_label)

        root.add_child(self._build_operation_params_panel())
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
        self.tree.on_select = self._on_tree_select
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

        self.operation_params_panel.padding = 8
        self.operation_params_panel.background_color = (0.10, 0.105, 0.12, 1.0)
        self.operation_params_panel.visible = False

        body = VStack()
        body.spacing = 5

        self.operation_params_title.text = "Operation"
        self.operation_params_title.color = (0.84, 0.88, 0.94, 1.0)
        body.add_child(self.operation_params_title)

        self.operation_params_kind.color = (0.58, 0.64, 0.72, 1.0)
        body.add_child(self.operation_params_kind)

        separator = Separator()
        separator.orientation = "horizontal"
        body.add_child(separator)

        vector_label = Label()
        vector_label.text = "Extrude vector"
        vector_label.color = (0.70, 0.74, 0.80, 1.0)
        body.add_child(vector_label)

        for axis in ("x", "y", "z"):
            body.add_child(self._build_vector_row(axis))

        self.operation_params_panel.add_child(body)
        return self.operation_params_panel

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
        title.text = f"Contour: {contour.name}"
        title.color = (0.84, 0.88, 0.94, 1.0)
        body.add_child(title)

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
        self.document = clear_document()
        self.draft = start_sketch_draft()
        self.selected_node_data = None
        self.current_path = None
        self.mode = "idle"
        self.refresh_tree()
        self.fit_camera()
        self.request_preview_rebuild()
        self._set_status("New document")
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

        self.document = state.document
        state.camera.apply_to(self.camera)
        self.selected_node_data = self._validated_selection(state.selection)
        self.draft = start_sketch_draft()
        self.mode = "idle"
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
        self.mode = "draw_sketch"
        self.draft = start_sketch_draft()
        self._refresh_labels()
        self.request_preview_rebuild()
        log.info("[CsgCad] mode=draw_sketch")

    def close_contour(self) -> None:
        result = close_draft_contour(self.document, self.draft)
        if not result.success:
            return
        self.selected_node_data = result.selection
        self.refresh_tree()
        self.request_preview_rebuild()
        contour_id = ""
        if result.contour is not None:
            contour_id = result.contour.id
        log.info(f"[CsgCad] contour closed id='{contour_id}'")

    def extrude_selected(self) -> None:
        sketch_id = selected_sketch_id(self.document, self.selected_node_data)
        result = add_extrude_for_selection(self.document, self.selected_node_data, 1.0)
        if not result.success:
            return
        self.selected_node_data = result.selection
        self.refresh_tree()
        self.fit_camera()
        self.request_preview_rebuild()
        operation_id = ""
        if result.operation is not None:
            operation_id = result.operation.id
        log.info(f"[CsgCad] extrude added id='{operation_id}' sketch='{sketch_id}'")

    def add_boolean_operation(self, kind: str) -> None:
        result = add_boolean_for_selection(self.document, self.selected_node_data, kind)
        if not result.success:
            return
        self.selected_node_data = result.selection
        self.refresh_tree()
        self.fit_camera()
        self.request_preview_rebuild()
        operation_id = ""
        if result.operation is not None:
            operation_id = result.operation.id
        self._set_status(f"{kind.capitalize()} added")
        log.info(f"[CsgCad] boolean added kind='{kind}' id='{operation_id}'")

    def fit_camera(self) -> None:
        lo, hi = document_bounds(self.document)
        self.camera.fit_bounds(lo, hi)
        self.request_render()

    def clear_document(self) -> None:
        self.document = clear_document()
        self.draft = start_sketch_draft()
        self.selected_node_data = None
        self.current_path = None
        self.mode = "idle"
        self.refresh_tree()
        self.fit_camera()
        self.request_preview_rebuild()
        self._set_status("Cleared")
        log.info("[CsgCad] document cleared")

    def refresh_tree(self) -> None:
        self.tree.clear()
        roots = build_document_tree(self.document)
        for root in roots:
            self.tree.add_root(self._to_tree_node(root))
        self._restore_tree_selection(self.tree.root_nodes)
        self._refresh_labels()
        self._refresh_operation_params_panel()
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
        self._refresh_operation_params_panel()
        self._refresh_plane_params_panel()
        self._refresh_contour_params_panel()
        self.request_preview_rebuild()

    def _on_scene_click(self, x: float, y: float, width: int, height: int) -> bool:
        if self.mode != "draw_sketch":
            return False
        ray_origin, ray_direction = self.camera.screen_ray(x, y, width, height)
        fallback_point = self.camera.world_point_on_z_plane(x, y, width, height, 0.0)
        result = add_draft_point_from_ray(
            self.document,
            self.draft,
            ray_origin,
            ray_direction,
            fallback_point=fallback_point,
            fallback_plane=ProceduralPlane(),
            fallback_kind="oxy",
        )
        if not result.success or result.point is None:
            return True
        self._refresh_labels()
        self.request_preview_rebuild()
        point = result.point
        log.info(
            "[CsgCad] draft point added "
            f"kind={result.kind} "
            f"point=({point[0]:.3f}, {point[1]:.3f}, {point[2]:.3f}) "
            f"count={len(self.draft.points)}"
        )
        return True

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
        if operation.kind != "extrude":
            self._set_operation_params_visible(False)
            return
        source_sketch_id = str(operation.params.get("source_sketch_id", ""))
        sketch = self.document.find_sketch(source_sketch_id)
        if sketch is None:
            self._set_operation_params_visible(False)
            log.error(
                "[CsgCad] cannot show extrude parameters: "
                f"source sketch not found '{source_sketch_id}'"
            )
            return

        vector = extrude_vector_for_operation(sketch, operation)
        self.operation_params_title.text = operation.name
        self.operation_params_kind.text = f"Kind: {operation.kind}"
        self._syncing_operation_params = True
        self.extrude_vector_inputs["x"].value = vector[0]
        self.extrude_vector_inputs["y"].value = vector[1]
        self.extrude_vector_inputs["z"].value = vector[2]
        self._syncing_operation_params = False
        self._set_operation_params_visible(True)

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

    def _set_operation_params_visible(self, visible: bool) -> None:
        if self.operation_params_panel.visible == visible:
            return
        self.operation_params_panel.visible = visible
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

    def _selected_operation(self):
        if self.selected_node_data is None:
            return None
        kind, item_id = self.selected_node_data
        if kind != "operation":
            return None
        return self.document.find_operation(item_id)

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
        for sketch in self.document.items:
            for contour in sketch.contours:
                if contour.id == item_id:
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
        if not set_extrude_vector(self.document, operation.id, vector):
            return
        self.refresh_tree()
        self.request_preview_rebuild()
        log.info(
            "[CsgCad] extrude vector changed "
            f"operation='{operation.id}' vector=({vector[0]:.3f}, {vector[1]:.3f}, {vector[2]:.3f})"
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
        if not set_sketch_plane(self.document, sketch.id, plane):
            return
        self.refresh_tree()
        self.request_preview_rebuild()
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
        if not set_contour_point(self.document, contour.id, point_index, point):
            return
        self.request_preview_rebuild()
        log.info(
            "[CsgCad] contour point changed "
            f"contour='{contour.id}' index={point_index} point=({point[0]:.3f}, {point[1]:.3f})"
        )

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
