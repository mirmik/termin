"""Standalone mini CAD application widget tree for procedural CSG documents."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from tcbase import log
from tcbase._geom_native import Vec4
from tcgui.widgets.file_dialog_overlay import show_open_file_dialog, show_save_file_dialog
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.menu import Menu, MenuItem
from tcgui.widgets.menu_bar import MenuBar
from tcgui.widgets.panel import Panel
from tcgui.widgets.splitter import Splitter
from tcgui.widgets.tree import TreeNode, TreeWidget
from tcgui.widgets.ui import UI
from tcgui.widgets.units import pct, px
from tcgui.widgets.vstack import VStack

from termin.csg.cad_viewer import CadViewportWidget, CsgSceneRenderer, document_bounds
from termin.csg.csg_editor_panel import CsgEditorPanel
from termin.csg.cad_state import CAD_STATE_FILTER, CadState, load_cad_state, save_cad_state
from termin.csg.document_edit import SketchDraft
from termin.csg.editor_controller import CsgEditorCommandResult, CsgEditorController
from termin.csg.document_tree_model import build_document_tree
from termin.csg.sketch_point_interaction import (
    SketchPointDrag,
    WallHeightDrag,
    drag_point_to_ray,
    drag_wall_height_offset_to_ray,
    pick_selected_sketch_point,
    pick_selected_wall_height_point,
)
from termin.csg.cad_tree_adapter import (
    boolean_operation_id_for_tree_node,
    boolean_parent_id_for_tree_node,
    restore_tree_selection,
    to_tree_node,
    tree_node_data,
    tree_node_model,
)
from termin.csg.procedural_document import (
    ProceduralMeshDocument,
    ProceduralPlane,
)
from termin.csg.viewer_camera import OrbitCamera


class CadApp:
    def __init__(self) -> None:
        self.ui: UI | None = None
        self.controller = CsgEditorController()
        self.camera = OrbitCamera()
        self.viewport = CadViewportWidget(self.camera)
        self.current_path: Path | None = None
        self.last_directory = Path.cwd()
        self.show_wireframe = True
        self._sketch_point_drag: SketchPointDrag | None = None
        self._wall_height_drag: WallHeightDrag | None = None
        self.editor_panel = CsgEditorPanel(
            self.controller,
            self._apply_controller_result,
            log_prefix="[CsgCad]",
            fit_callback=self.fit_camera,
            clear_callback=self.clear_document,
            request_layout=self._request_layout,
            wireframe_getter=self._wireframe_visible,
            wireframe_setter=self._set_wireframe_visible,
        )

        self.file_label = Label()
        self.tree = TreeWidget()
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
        root.preferred_width = pct(100)
        root.preferred_height = pct(100)
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
        self._set_wireframe_visible(bool(checked))

    def _wireframe_visible(self) -> bool:
        return self.show_wireframe

    def _set_wireframe_visible(self, visible: bool) -> None:
        self.show_wireframe = bool(visible)
        self.request_preview_rebuild()
        log.info(f"[CsgCad] wireframe visible={self.show_wireframe}")

    def _request_layout(self) -> None:
        if self.ui is not None:
            self.ui.request_layout()

    def _build_side_panel(self):
        root = VStack()
        root.spacing = 6

        title = Label()
        title.text = "CSG CAD"
        root.add_child(title)

        self.file_label.color = (0.58, 0.64, 0.72, 1.0)
        root.add_child(self.file_label)

        root.add_child(self.editor_panel.build())

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
        self.editor_panel.start_draw_sketch()

    def start_add_outer_contour(self) -> None:
        self.editor_panel.start_add_outer_contour()

    def start_add_hole_contour(self) -> None:
        self.editor_panel.start_add_hole_contour()

    def start_add_wall_path(self) -> None:
        self.editor_panel.start_add_wall_path()

    def close_contour(self) -> None:
        self.editor_panel.close_contour()

    def finish_wall_path(self) -> None:
        self.editor_panel.finish_wall_path()

    def extrude_selected(self) -> None:
        self.editor_panel.extrude_selected()

    def wall_selected(self) -> None:
        self.editor_panel.wall_selected()

    def add_boolean_operation(self, kind: str) -> None:
        self.editor_panel.add_boolean_operation(kind)

    def add_primitive(self, kind: str) -> None:
        self.editor_panel.add_primitive(kind)

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
                self.editor_panel.refresh_all()
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
            self.tree.add_root(to_tree_node(root))
        restore_tree_selection(self.tree, self.tree.root_nodes, self.selected_node_data)
        self._refresh_labels()
        self.editor_panel.refresh_all()
        if self.tree._ui is not None:
            self.tree._ui.request_layout()

    def _on_tree_select(self, node: TreeNode) -> None:
        self.selected_node_data = node.data
        self._refresh_labels()
        self.editor_panel.refresh_all()
        self.request_preview_rebuild()

    def _on_tree_drop(self, dragged_node: TreeNode, target_node: TreeNode | None, position: str) -> None:
        dragged_data = tree_node_data(dragged_node)
        if dragged_data is None or dragged_data[0] != "operation":
            log.error("[CsgCad] cannot drop tree node: drag an operation node")
            return
        dragged_operation_id = dragged_data[1]
        if self.document.find_operation(dragged_operation_id) is None:
            log.error(f"[CsgCad] cannot drop tree node: operation not found '{dragged_operation_id}'")
            return

        source_boolean_id = boolean_parent_id_for_tree_node(self.document, dragged_node)
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
            target_boolean_id = boolean_operation_id_for_tree_node(self.document, target_node)
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

        target_model = tree_node_model(target_node)
        if target_model is None or not target_model.accepts_drop_above_below:
            log.error("[CsgCad] cannot reorder boolean input: drop above or below an input inside a boolean operation")
            return
        target_boolean_id = target_model.parent_operation_id
        target_operation = self.document.find_operation(target_boolean_id)
        if target_operation is None:
            log.error(f"[CsgCad] cannot reorder boolean input: boolean operation not found '{target_boolean_id}'")
            return
        if target_model.input_index < 0 or target_model.input_index >= len(target_operation.inputs):
            log.error(f"[CsgCad] cannot reorder boolean input: invalid target input index {target_model.input_index}")
            return
        insert_index = target_model.input_index + (1 if position == "below" else 0)
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

    def _on_scene_mouse_down(self, x: float, y: float, width: int, height: int) -> bool:
        wall_drag = self._pick_selected_wall_height_point(x, y, width, height)
        if wall_drag is not None:
            self._wall_height_drag = wall_drag
            self._set_status(f"Dragging wall height P{wall_drag.point_index}")
            log.info(
                "[CsgCad] wall height drag started "
                f"operation='{wall_drag.operation_id}' source='{wall_drag.source_id}' index={wall_drag.point_index}"
            )
            return True
        drag = self._pick_selected_sketch_point(x, y, width, height)
        if drag is None:
            return False
        self._sketch_point_drag = drag
        self._set_status(f"Dragging {drag.kind} point P{drag.point_index}")
        log.info(
            "[CsgCad] sketch point drag started "
            f"kind='{drag.kind}' item='{drag.item_id}' index={drag.point_index}"
        )
        return True

    def _on_scene_mouse_move(self, x: float, y: float, width: int, height: int) -> bool:
        if self._wall_height_drag is not None:
            return self._drag_wall_height_to_screen(x, y, width, height)
        if self._sketch_point_drag is None:
            return False
        return self._drag_sketch_point_to_screen(x, y, width, height)

    def _on_scene_mouse_up(self, x: float, y: float, width: int, height: int) -> bool:
        wall_drag = self._wall_height_drag
        if wall_drag is not None:
            self._drag_wall_height_to_screen(x, y, width, height)
            self._wall_height_drag = None
            self._set_status(f"Wall height P{wall_drag.point_index} moved")
            log.info(
                "[CsgCad] wall height drag finished "
                f"operation='{wall_drag.operation_id}' source='{wall_drag.source_id}' index={wall_drag.point_index}"
            )
            return True
        drag = self._sketch_point_drag
        if drag is None:
            return False
        self._drag_sketch_point_to_screen(x, y, width, height)
        self._sketch_point_drag = None
        self._set_status(f"{drag.kind.capitalize()} point P{drag.point_index} moved")
        log.info(
            "[CsgCad] sketch point drag finished "
            f"kind='{drag.kind}' item='{drag.item_id}' index={drag.point_index}"
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

    def _pick_selected_sketch_point(
        self,
        x: float,
        y: float,
        width: int,
        height: int,
    ) -> SketchPointDrag | None:
        return pick_selected_sketch_point(
            self.document,
            self.selected_node_data,
            lambda point: self._project_world_to_screen(point, width, height),
            x,
            y,
        )

    def _pick_selected_wall_height_point(
        self,
        x: float,
        y: float,
        width: int,
        height: int,
    ) -> WallHeightDrag | None:
        return pick_selected_wall_height_point(
            self.document,
            self.selected_node_data,
            lambda point: self._project_world_to_screen(point, width, height),
            x,
            y,
        )

    def _drag_sketch_point_to_screen(self, x: float, y: float, width: int, height: int) -> bool:
        drag = self._sketch_point_drag
        if drag is None:
            return False
        ray_origin, ray_direction = self.camera.screen_ray(x, y, width, height)
        local_point = drag_point_to_ray(self.document, drag, ray_origin, ray_direction)
        if local_point is None:
            return True
        if drag.kind == "contour":
            result = self.controller.set_contour_point(drag.item_id, drag.point_index, local_point)
        elif drag.kind == "path":
            result = self.controller.set_path_point(drag.item_id, drag.point_index, local_point)
        else:
            log.error(f"[CsgCad] cannot drag sketch point: unsupported kind '{drag.kind}'")
            return True
        if not result.success:
            return True
        if drag.kind == "contour":
            self.editor_panel.sync_contour_point_inputs(drag.point_index, local_point)
        self.request_preview_rebuild()
        return True

    def _drag_wall_height_to_screen(self, x: float, y: float, width: int, height: int) -> bool:
        drag = self._wall_height_drag
        if drag is None:
            return False
        ray_origin, ray_direction = self.camera.screen_ray(x, y, width, height)
        offset = drag_wall_height_offset_to_ray(drag, ray_origin, ray_direction)
        result = self.controller.set_wall_corner_offset(drag.operation_id, drag.source_id, drag.point_index, offset)
        if not result.success:
            return True
        self.editor_panel.sync_wall_corner_offset_input(drag.source_id, drag.point_index, offset)
        self.request_preview_rebuild()
        return True

    def _project_world_to_screen(
        self,
        point: tuple[float, float, float],
        width: int,
        height: int,
    ) -> tuple[float, float] | None:
        mvp = self.camera.view_projection(width, height)
        clip = mvp.transform_vec4(Vec4(float(point[0]), float(point[1]), float(point[2]), 1.0))
        w = float(clip.w)
        if w <= 1.0e-8:
            return None
        return (
            float((clip.x / w + 1.0) * 0.5 * float(width)),
            float((clip.y / w + 1.0) * 0.5 * float(height)),
        )

    def _refresh_labels(self) -> None:
        if self.current_path is None:
            self.file_label.text = "File: <unsaved>"
        else:
            self.file_label.text = f"File: {self.current_path.name}"
        self.editor_panel.refresh_labels()

    def _set_status(self, text: str) -> None:
        self.editor_panel.set_status(text)

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
        if kind == "path":
            for item in self.document.items:
                for path in item.paths:
                    if path.id == item_id:
                        return selection
        log.error(f"[CsgCad] saved selection is missing kind='{kind}' id='{item_id}'")
        return None


def run_cad_app(title: str = "termin-csg CAD", size: tuple[int, int] = (1200, 760)) -> None:
    from termin.csg.cad_runtime import run_cad_app as _run_cad_app

    _run_cad_app(title, size)


__all__ = [
    "CadApp",
    "run_cad_app",
]
