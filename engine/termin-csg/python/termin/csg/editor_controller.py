"""Headless editor controller for procedural CSG documents."""

from __future__ import annotations

from dataclasses import dataclass

from tcbase import log

from termin.csg.document_edit import (
    SelectionData,
    SketchDraft,
    add_boolean_for_selection,
    add_boolean_input,
    add_draft_point_from_ray,
    add_extrude_for_selection,
    add_primitive_operation,
    add_wall_for_selection,
    clear_document,
    close_draft_contour,
    finish_draft_path,
    move_boolean_input,
    remove_boolean_input,
    set_contour_point,
    set_extrude_vector,
    set_operation_transform,
    set_path_point,
    set_primitive_params,
    set_sketch_plane,
    set_wall_corner_offset,
    set_wall_params,
    start_sketch_draft,
)
from termin.csg.procedural_document import (
    CONTOUR_ROLE_HOLE,
    CONTOUR_ROLE_OUTER,
    ContourDocument,
    ProceduralMeshDocument,
    ProceduralPlane,
    SketchItemDocument,
)

Vec2Data = tuple[float, float]
Vec3Data = tuple[float, float, float]


@dataclass
class CsgEditorCommandResult:
    success: bool
    message: str = ""
    document_changed: bool = False
    selection_changed: bool = False
    tree_changed: bool = False
    preview_changed: bool = False
    fit_camera: bool = False

    @classmethod
    def failed(cls, message: str = "") -> "CsgEditorCommandResult":
        return cls(False, message=message)

    @classmethod
    def changed(
        cls,
        message: str = "",
        *,
        selection_changed: bool = False,
        tree_changed: bool = True,
        preview_changed: bool = True,
        fit_camera: bool = False,
    ) -> "CsgEditorCommandResult":
        return cls(
            True,
            message=message,
            document_changed=True,
            selection_changed=selection_changed,
            tree_changed=tree_changed,
            preview_changed=preview_changed,
            fit_camera=fit_camera,
        )


class CsgEditorController:
    """Owns document edit state that must be shared by standalone and app editors."""

    def __init__(self, document: ProceduralMeshDocument | None = None) -> None:
        self.document = document if document is not None else ProceduralMeshDocument()
        self.draft: SketchDraft = start_sketch_draft()
        self.selection: SelectionData | None = None
        self.mode = "idle"

    def replace_document(
        self,
        document: ProceduralMeshDocument,
        selection: SelectionData | None = None,
    ) -> CsgEditorCommandResult:
        self.document = document
        self.draft = start_sketch_draft()
        self.selection = selection
        self.mode = "idle"
        return CsgEditorCommandResult.changed(
            "Document loaded",
            selection_changed=True,
            fit_camera=True,
        )

    def new_document(self) -> CsgEditorCommandResult:
        self.document = clear_document()
        self.draft = start_sketch_draft()
        self.selection = None
        self.mode = "idle"
        return CsgEditorCommandResult.changed(
            "Cleared",
            selection_changed=True,
            fit_camera=True,
        )

    def select_node(self, selection: SelectionData | None) -> CsgEditorCommandResult:
        self.selection = selection
        return CsgEditorCommandResult(
            True,
            selection_changed=True,
            preview_changed=True,
        )

    def start_draw_sketch(self) -> CsgEditorCommandResult:
        self.mode = "draw_sketch"
        self.draft = start_sketch_draft()
        return CsgEditorCommandResult(True, "Drawing sketch", preview_changed=True)

    def cancel_current_tool(self) -> CsgEditorCommandResult:
        self.mode = "idle"
        self.draft = start_sketch_draft()
        return CsgEditorCommandResult(True, "Tool cleared", preview_changed=True)

    def start_add_outer_contour(self) -> CsgEditorCommandResult:
        sketch = self.selected_sketch()
        if sketch is None:
            log.error("[CsgEditorController] cannot add outer contour: select a sketch")
            return CsgEditorCommandResult.failed("Select a sketch")
        self.mode = "draw_sketch"
        self.draft = start_sketch_draft(
            sketch_id=sketch.id,
            plane=sketch.plane,
            contour_role=CONTOUR_ROLE_OUTER,
        )
        return CsgEditorCommandResult(True, f"Adding outer contour to {sketch.name}", preview_changed=True)

    def start_add_hole_contour(self) -> CsgEditorCommandResult:
        contour_ref = self.selected_contour_ref()
        if contour_ref is None:
            log.error("[CsgEditorController] cannot add hole contour: select an outer contour")
            return CsgEditorCommandResult.failed("Select an outer contour")
        sketch, contour = contour_ref
        if contour.role != CONTOUR_ROLE_OUTER:
            log.error(f"[CsgEditorController] cannot add hole contour: selected contour is not outer '{contour.id}'")
            return CsgEditorCommandResult.failed("Select an outer contour")
        self.mode = "draw_sketch"
        self.draft = start_sketch_draft(
            sketch_id=sketch.id,
            plane=sketch.plane,
            contour_role=CONTOUR_ROLE_HOLE,
            parent_contour_id=contour.id,
        )
        return CsgEditorCommandResult(True, f"Adding hole to {contour.name}", preview_changed=True)

    def start_add_wall_path(self) -> CsgEditorCommandResult:
        sketch = self.selected_sketch()
        if sketch is None:
            log.error("[CsgEditorController] cannot add wall path: select a sketch")
            return CsgEditorCommandResult.failed("Select a sketch")
        self.mode = "draw_sketch"
        self.draft = start_sketch_draft(
            sketch_id=sketch.id,
            plane=sketch.plane,
            purpose="wall",
        )
        return CsgEditorCommandResult(True, f"Adding wall path to {sketch.name}", preview_changed=True)

    def add_draft_point_from_ray(
        self,
        ray_origin: Vec3Data,
        ray_direction: Vec3Data,
        fallback_point: Vec3Data | None = None,
        fallback_plane: ProceduralPlane | None = None,
        fallback_kind: str = "fallback",
    ) -> CsgEditorCommandResult:
        result = add_draft_point_from_ray(
            self.document,
            self.draft,
            ray_origin,
            ray_direction,
            fallback_point=fallback_point,
            fallback_plane=fallback_plane,
            fallback_kind=fallback_kind,
        )
        if not result.success:
            return CsgEditorCommandResult.failed()
        return CsgEditorCommandResult(True, preview_changed=True)

    def close_contour(self) -> CsgEditorCommandResult:
        result = close_draft_contour(self.document, self.draft)
        if not result.success:
            return CsgEditorCommandResult.failed()
        self.mode = "idle"
        self.selection = result.selection
        return CsgEditorCommandResult.changed(
            "Contour closed",
            selection_changed=True,
            tree_changed=True,
            preview_changed=True,
        )

    def finish_wall_path(self) -> CsgEditorCommandResult:
        result = finish_draft_path(self.document, self.draft, purpose="wall")
        if not result.success:
            return CsgEditorCommandResult.failed()
        self.mode = "idle"
        self.selection = result.selection
        return CsgEditorCommandResult.changed(
            "Wall path finished",
            selection_changed=True,
            tree_changed=True,
            preview_changed=True,
        )

    def extrude_selected(self) -> CsgEditorCommandResult:
        result = add_extrude_for_selection(self.document, self.selection, 1.0)
        if not result.success:
            return CsgEditorCommandResult.failed()
        self.selection = result.selection
        return CsgEditorCommandResult.changed(
            "Extrude added",
            selection_changed=True,
            tree_changed=True,
            preview_changed=True,
            fit_camera=True,
        )

    def wall_selected(self) -> CsgEditorCommandResult:
        result = add_wall_for_selection(self.document, self.selection)
        if not result.success:
            return CsgEditorCommandResult.failed()
        self.selection = result.selection
        return CsgEditorCommandResult.changed(
            "Wall added",
            selection_changed=True,
            tree_changed=True,
            preview_changed=True,
            fit_camera=True,
        )

    def add_boolean_operation(self, kind: str) -> CsgEditorCommandResult:
        result = add_boolean_for_selection(self.document, self.selection, kind)
        if not result.success:
            return CsgEditorCommandResult.failed()
        self.selection = result.selection
        return CsgEditorCommandResult.changed(
            f"{kind.capitalize()} added",
            selection_changed=True,
            tree_changed=True,
            preview_changed=True,
            fit_camera=True,
        )

    def add_primitive(self, kind: str) -> CsgEditorCommandResult:
        result = add_primitive_operation(self.document, kind)
        if not result.success:
            return CsgEditorCommandResult.failed()
        self.selection = result.selection
        return CsgEditorCommandResult.changed(
            f"{kind.capitalize()} added",
            selection_changed=True,
            tree_changed=True,
            preview_changed=True,
            fit_camera=True,
        )

    def add_boolean_input(
        self,
        boolean_operation_id: str,
        input_operation_id: str,
        insert_index: int | None = None,
    ) -> CsgEditorCommandResult:
        if not add_boolean_input(self.document, boolean_operation_id, input_operation_id, insert_index):
            return CsgEditorCommandResult.failed()
        self.selection = ("operation", input_operation_id)
        return CsgEditorCommandResult.changed(
            f"Added input to {boolean_operation_id[:10]}",
            selection_changed=True,
            tree_changed=True,
            preview_changed=True,
        )

    def move_boolean_input(
        self,
        source_boolean_operation_id: str,
        target_boolean_operation_id: str,
        input_operation_id: str,
        insert_index: int | None = None,
    ) -> CsgEditorCommandResult:
        if not move_boolean_input(
            self.document,
            source_boolean_operation_id,
            target_boolean_operation_id,
            input_operation_id,
            insert_index,
        ):
            return CsgEditorCommandResult.failed()
        self.selection = ("operation", input_operation_id)
        return CsgEditorCommandResult.changed(
            f"Moved input in {target_boolean_operation_id[:10]}",
            selection_changed=True,
            tree_changed=True,
            preview_changed=True,
        )

    def remove_boolean_input(
        self,
        boolean_operation_id: str,
        input_operation_id: str,
    ) -> CsgEditorCommandResult:
        if not remove_boolean_input(self.document, boolean_operation_id, input_operation_id):
            return CsgEditorCommandResult.failed()
        self.selection = ("operation", input_operation_id)
        return CsgEditorCommandResult.changed(
            f"Removed input from {boolean_operation_id[:10]}",
            selection_changed=True,
            tree_changed=True,
            preview_changed=True,
        )

    def set_extrude_vector(self, operation_id: str, vector: Vec3Data) -> CsgEditorCommandResult:
        if not set_extrude_vector(self.document, operation_id, vector):
            return CsgEditorCommandResult.failed()
        return CsgEditorCommandResult.changed(tree_changed=True, preview_changed=True)

    def set_operation_transform(
        self,
        operation_id: str,
        center: Vec3Data,
        rotation: Vec3Data,
    ) -> CsgEditorCommandResult:
        if not set_operation_transform(self.document, operation_id, center, rotation):
            return CsgEditorCommandResult.failed()
        return CsgEditorCommandResult.changed(tree_changed=False, preview_changed=True)

    def set_primitive_params(self, operation_id: str, params: dict) -> CsgEditorCommandResult:
        if not set_primitive_params(self.document, operation_id, params):
            return CsgEditorCommandResult.failed()
        return CsgEditorCommandResult.changed(tree_changed=True, preview_changed=True)

    def set_wall_params(
        self,
        operation_id: str,
        height: float,
        thickness: float,
        alignment: str,
    ) -> CsgEditorCommandResult:
        if not set_wall_params(self.document, operation_id, height, thickness, alignment):
            return CsgEditorCommandResult.failed()
        return CsgEditorCommandResult.changed(tree_changed=True, preview_changed=True)

    def set_wall_corner_offset(
        self,
        operation_id: str,
        source_id: str,
        point_index: int,
        offset: float,
    ) -> CsgEditorCommandResult:
        if not set_wall_corner_offset(self.document, operation_id, source_id, point_index, offset):
            return CsgEditorCommandResult.failed()
        return CsgEditorCommandResult.changed(tree_changed=False, preview_changed=True)

    def set_sketch_plane(self, sketch_id: str, plane: ProceduralPlane) -> CsgEditorCommandResult:
        if not set_sketch_plane(self.document, sketch_id, plane):
            return CsgEditorCommandResult.failed()
        return CsgEditorCommandResult.changed(tree_changed=True, preview_changed=True)

    def set_contour_point(
        self,
        contour_id: str,
        point_index: int,
        point: Vec2Data,
    ) -> CsgEditorCommandResult:
        if not set_contour_point(self.document, contour_id, point_index, point):
            return CsgEditorCommandResult.failed()
        return CsgEditorCommandResult.changed(tree_changed=False, preview_changed=True)

    def set_path_point(
        self,
        path_id: str,
        point_index: int,
        point: Vec2Data,
    ) -> CsgEditorCommandResult:
        if not set_path_point(self.document, path_id, point_index, point):
            return CsgEditorCommandResult.failed()
        return CsgEditorCommandResult.changed(tree_changed=False, preview_changed=True)

    def selected_sketch(self) -> SketchItemDocument | None:
        if self.selection is None:
            return None
        kind, item_id = self.selection
        if kind == "sketch":
            return self.document.find_sketch(item_id)
        if kind == "contour":
            contour_ref = self.document.find_contour_ref(item_id)
            if contour_ref is not None:
                return contour_ref[0]
        if kind == "path":
            path_ref = self.document.find_path_ref(item_id)
            if path_ref is not None:
                return path_ref[0]
        return None

    def selected_contour_ref(self) -> tuple[SketchItemDocument, ContourDocument] | None:
        if self.selection is None:
            return None
        kind, item_id = self.selection
        if kind != "contour":
            return None
        return self.document.find_contour_ref(item_id)


__all__ = [
    "CsgEditorCommandResult",
    "CsgEditorController",
]
