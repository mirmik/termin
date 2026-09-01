"""Toolkit-neutral application model for the standalone procedural CSG CAD."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from termin.base import log
from termin.base._geom_native import Vec3

from termin.csg.cad_state import CadState, load_cad_state, save_cad_state
from termin.csg.cad_viewer import document_bounds
from termin.csg.document_tree_model import document_summary
from termin.csg.editor_controller import CsgEditorCommandResult, CsgEditorController
from termin.csg.procedural_document import ProceduralPlane
from termin.csg.sketch_point_interaction import (
    SketchPointDrag,
    WallHeightDrag,
    drag_point_to_ray,
    drag_wall_height_offset_to_ray,
    pick_selected_sketch_point,
    pick_selected_wall_height_point,
)
from termin.csg.viewer_camera import OrbitCamera


@dataclass(frozen=True)
class StandaloneCsgSnapshot:
    mode: str
    draft_point_count: int
    document_summary: str
    selection: tuple[str, str] | None
    status: str


class StandaloneCsgModel:
    """Own standalone CAD state without depending on a widget toolkit."""

    def __init__(self, request_render: Callable[[], None]) -> None:
        self.controller = CsgEditorController()
        self.camera = OrbitCamera()
        self.current_path: Path | None = None
        self.last_directory = Path.cwd()
        self.show_wireframe = True
        self.dirty = True
        self.preview_revision = 0
        self._status = "Ready"
        self._changed_handler: Callable[[StandaloneCsgSnapshot], None] | None = None
        self._request_render_callback = request_render
        self._sketch_point_drag: SketchPointDrag | None = None
        self._wall_height_drag: WallHeightDrag | None = None

    @property
    def snapshot(self) -> StandaloneCsgSnapshot:
        return StandaloneCsgSnapshot(
            mode=self.controller.mode,
            draft_point_count=len(self.controller.draft.points),
            document_summary=document_summary(self.controller.document),
            selection=self.controller.selection,
            status=self._status,
        )

    def set_changed_handler(
        self,
        handler: Callable[[StandaloneCsgSnapshot], None] | None,
    ) -> None:
        self._changed_handler = handler
        if handler is not None:
            handler(self.snapshot)

    def set_status(self, status: str) -> None:
        self._status = status
        self._notify_changed()

    def request_render(self) -> None:
        self.dirty = True
        self._request_render_callback()

    def request_preview_rebuild(self) -> None:
        self.preview_revision += 1
        self.request_render()

    def apply_result(
        self,
        result: CsgEditorCommandResult,
        default_status: str = "",
    ) -> bool:
        if not result.success:
            if result.message:
                self._status = result.message
                log.error(f"[CsgCad] command failed: {result.message}")
                self._notify_changed()
            return False
        if result.fit_camera:
            self.fit_camera()
        if result.preview_changed:
            self.request_preview_rebuild()
        status = result.message if result.message else default_status
        if status:
            self._status = status
        self._notify_changed()
        return True

    def new_document(self) -> bool:
        self.current_path = None
        changed = self.apply_result(self.controller.new_document(), "New document")
        if changed:
            log.info("[CsgCad] new document")
        return changed

    def clear_document(self) -> bool:
        self.current_path = None
        changed = self.apply_result(self.controller.new_document(), "Cleared")
        if changed:
            log.info("[CsgCad] document cleared")
        return changed

    def save_state(self, path: str | Path | None = None) -> bool:
        target = self.current_path if path is None else Path(path).expanduser()
        if target is None:
            self.set_status("Save path is required")
            return False
        try:
            saved_path = save_cad_state(
                target,
                CadState.from_app_state(
                    self.controller.document,
                    self.camera,
                    self.controller.selection,
                ),
            )
        except Exception as error:
            self.set_status("Save failed")
            log.error(f"[CsgCad] failed to save state path='{target}': {error}")
            return False
        self.current_path = saved_path
        self.last_directory = saved_path.parent
        self.set_status(f"Saved: {saved_path.name}")
        log.info(f"[CsgCad] state saved path='{saved_path}'")
        return True

    def load_state(self, path: str | Path) -> bool:
        target = Path(path).expanduser()
        try:
            state = load_cad_state(target)
        except Exception as error:
            self.set_status("Open failed")
            log.error(f"[CsgCad] failed to load state path='{target}': {error}")
            return False
        self.controller.replace_document(state.document)
        state.camera.apply_to(self.camera)
        self.controller.selection = self._validated_selection(state.selection)
        self.current_path = target
        self.last_directory = target.parent
        self.request_preview_rebuild()
        self.set_status(f"Opened: {target.name}")
        log.info(f"[CsgCad] state loaded path='{target}'")
        return True

    def file_dialog_directory(self) -> Path:
        return self.current_path.parent if self.current_path is not None else self.last_directory

    def fit_camera(self) -> None:
        lo, hi = document_bounds(self.controller.document)
        self.camera.fit_bounds(lo, hi)
        self.request_render()

    def set_wireframe_visible(self, visible: bool) -> None:
        resolved = bool(visible)
        if self.show_wireframe == resolved:
            return
        self.show_wireframe = resolved
        self.request_preview_rebuild()
        log.info(f"[CsgCad] wireframe visible={resolved}")

    def select_node(self, selection: tuple[str, str] | None) -> bool:
        return self.apply_result(self.controller.select_node(selection))

    def start_draw_sketch(self) -> bool:
        return self.apply_result(self.controller.start_draw_sketch())

    def start_add_outer_contour(self) -> bool:
        return self.apply_result(self.controller.start_add_outer_contour())

    def start_add_hole_contour(self) -> bool:
        return self.apply_result(self.controller.start_add_hole_contour())

    def start_add_wall_path(self) -> bool:
        return self.apply_result(self.controller.start_add_wall_path())

    def close_contour(self) -> bool:
        return self.apply_result(self.controller.close_contour())

    def finish_wall_path(self) -> bool:
        return self.apply_result(self.controller.finish_wall_path())

    def clear_tool(self) -> bool:
        return self.apply_result(self.controller.cancel_current_tool())

    def add_primitive(self, kind: str) -> bool:
        return self.apply_result(self.controller.add_primitive(kind), f"{kind.title()} added")

    def add_boolean_operation(self, kind: str) -> bool:
        return self.apply_result(self.controller.add_boolean_operation(kind))

    def extrude_selected(self) -> bool:
        return self.apply_result(self.controller.extrude_selected())

    def wall_selected(self) -> bool:
        return self.apply_result(self.controller.wall_selected())

    def set_primitive_params(self, operation_id: str, params: dict) -> bool:
        return self.apply_result(
            self.controller.set_primitive_params(operation_id, params),
            "Parameters updated",
        )

    def set_extrude_vector(self, operation_id: str, vector: tuple[float, float, float]) -> bool:
        return self.apply_result(
            self.controller.set_extrude_vector(operation_id, vector),
            "Extrude vector updated",
        )

    def set_operation_transform(
        self,
        operation_id: str,
        center: tuple[float, float, float],
        rotation: tuple[float, float, float],
    ) -> bool:
        return self.apply_result(
            self.controller.set_operation_transform(operation_id, center, rotation),
            "Transform updated",
        )

    def set_wall_params(
        self,
        operation_id: str,
        height: float,
        thickness: float,
        alignment: str,
    ) -> bool:
        return self.apply_result(
            self.controller.set_wall_params(operation_id, height, thickness, alignment),
            "Wall parameters updated",
        )

    def set_wall_corner_offset(
        self,
        operation_id: str,
        source_id: str,
        point_index: int,
        offset: float,
    ) -> bool:
        return self.apply_result(
            self.controller.set_wall_corner_offset(operation_id, source_id, point_index, offset),
            "Wall corner updated",
        )

    def set_sketch_plane(self, sketch_id: str, plane) -> bool:
        return self.apply_result(
            self.controller.set_sketch_plane(sketch_id, plane),
            "Sketch plane updated",
        )

    def set_contour_point(self, contour_id: str, point_index: int, point: tuple[float, float]) -> bool:
        return self.apply_result(
            self.controller.set_contour_point(contour_id, point_index, point),
            "Contour point updated",
        )

    def set_path_point(self, path_id: str, point_index: int, point: tuple[float, float]) -> bool:
        return self.apply_result(
            self.controller.set_path_point(path_id, point_index, point),
            "Path point updated",
        )

    def scene_mouse_down(self, x: float, y: float, width: int, height: int) -> bool:
        wall_drag = pick_selected_wall_height_point(
            self.controller.document,
            self.controller.selection,
            lambda point: self._project_world_to_screen(point, width, height),
            x,
            y,
        )
        if wall_drag is not None:
            self._wall_height_drag = wall_drag
            self.set_status(f"Dragging wall height P{wall_drag.point_index}")
            return True
        sketch_drag = pick_selected_sketch_point(
            self.controller.document,
            self.controller.selection,
            lambda point: self._project_world_to_screen(point, width, height),
            x,
            y,
        )
        if sketch_drag is None:
            return False
        self._sketch_point_drag = sketch_drag
        self.set_status(f"Dragging {sketch_drag.kind} point P{sketch_drag.point_index}")
        return True

    def scene_mouse_move(self, x: float, y: float, width: int, height: int) -> bool:
        if self._wall_height_drag is not None:
            return self._drag_wall_height(x, y, width, height)
        return self._drag_sketch_point(x, y, width, height)

    def scene_mouse_up(self, x: float, y: float, width: int, height: int) -> bool:
        if self._wall_height_drag is not None:
            drag = self._wall_height_drag
            self._drag_wall_height(x, y, width, height)
            self._wall_height_drag = None
            self.set_status(f"Wall height P{drag.point_index} moved")
            return True
        if self._sketch_point_drag is not None:
            drag = self._sketch_point_drag
            self._drag_sketch_point(x, y, width, height)
            self._sketch_point_drag = None
            self.set_status(f"{drag.kind.capitalize()} point P{drag.point_index} moved")
            return True
        return False

    def scene_click(self, x: float, y: float, width: int, height: int) -> bool:
        if self.controller.mode != "draw_sketch":
            return False
        ray = self.camera.screen_ray(x, y, width, height)
        fallback_point = self.camera.world_point_on_z_plane(x, y, width, height, 0.0)
        return self.apply_result(
            self.controller.add_draft_point_from_ray(
                ray,
                fallback_point=fallback_point,
                fallback_plane=ProceduralPlane(),
                fallback_kind="oxy",
            )
        )

    def _drag_sketch_point(self, x: float, y: float, width: int, height: int) -> bool:
        drag = self._sketch_point_drag
        if drag is None:
            return False
        ray = self.camera.screen_ray(x, y, width, height)
        local_point = drag_point_to_ray(self.controller.document, drag, ray)
        if local_point is None:
            return True
        if drag.kind == "contour":
            result = self.controller.set_contour_point(drag.item_id, drag.point_index, local_point)
        elif drag.kind == "path":
            result = self.controller.set_path_point(drag.item_id, drag.point_index, local_point)
        else:
            log.error(f"[CsgCad] cannot drag sketch point: unsupported kind '{drag.kind}'")
            return True
        if result.success:
            self.request_preview_rebuild()
            self._notify_changed()
        return True

    def _drag_wall_height(self, x: float, y: float, width: int, height: int) -> bool:
        drag = self._wall_height_drag
        if drag is None:
            return False
        ray = self.camera.screen_ray(x, y, width, height)
        offset = drag_wall_height_offset_to_ray(drag, ray)
        if offset is None:
            log.error("[CsgCad] cannot drag wall height: camera ray is invalid")
            return True
        result = self.controller.set_wall_corner_offset(
            drag.operation_id,
            drag.source_id,
            drag.point_index,
            offset,
        )
        if result.success:
            self.request_preview_rebuild()
            self._notify_changed()
        return True

    def _project_world_to_screen(
        self,
        point: tuple[float, float, float],
        width: int,
        height: int,
    ) -> tuple[float, float] | None:
        return self.camera.project_world_to_screen(
            Vec3(float(point[0]), float(point[1]), float(point[2])),
            width,
            height,
        )

    def _validated_selection(self, selection: tuple[str, str] | None) -> tuple[str, str] | None:
        if selection is None:
            return None
        kind, item_id = selection
        document = self.controller.document
        if kind in {"sketch", "plane"} and document.find_sketch(item_id) is not None:
            return selection
        if kind == "operation" and document.find_operation(item_id) is not None:
            return selection
        collection = (
            (contour for sketch in document.items for contour in sketch.contours)
            if kind == "contour"
            else (path for sketch in document.items for path in sketch.paths)
        )
        if kind in {"contour", "path"} and any(item.id == item_id for item in collection):
            return selection
        log.error(f"[CsgCad] saved selection is missing kind='{kind}' id='{item_id}'")
        return None

    def _notify_changed(self) -> None:
        handler = self._changed_handler
        if handler is not None:
            handler(self.snapshot)


__all__ = ["StandaloneCsgModel", "StandaloneCsgSnapshot"]
