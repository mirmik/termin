"""Shared edit operations for procedural CSG documents."""

from __future__ import annotations

from dataclasses import dataclass, field

from tcbase import log

from termin.csg.document_raycast import (
    ray_plane_intersection,
    raycast_document,
    sketch_plane_from_hit,
)
from termin.csg.procedural_document import (
    ContourDocument,
    OperationDocument,
    ProceduralMeshDocument,
    ProceduralPlane,
)

Vec3Data = tuple[float, float, float]
SelectionData = tuple[str, str]


@dataclass
class SketchDraft:
    points: list[Vec3Data] = field(default_factory=list)
    plane: ProceduralPlane | None = None


@dataclass
class DrawPointResult:
    success: bool
    point: Vec3Data | None = None
    kind: str = ""


@dataclass
class DocumentEditResult:
    success: bool
    selection: SelectionData | None = None
    contour: ContourDocument | None = None
    operation: OperationDocument | None = None


def start_sketch_draft() -> SketchDraft:
    return SketchDraft()


def clear_document() -> ProceduralMeshDocument:
    return ProceduralMeshDocument()


def add_draft_point_from_ray(
    document: ProceduralMeshDocument,
    draft: SketchDraft,
    ray_origin: Vec3Data,
    ray_direction: Vec3Data,
    fallback_point: Vec3Data | None = None,
    fallback_plane: ProceduralPlane | None = None,
    fallback_kind: str = "fallback",
) -> DrawPointResult:
    if draft.points:
        if draft.plane is None:
            log.error("[CsgDocumentEdit] cannot add draft point: active sketch plane is not available")
            return DrawPointResult(False)
        point = ray_plane_intersection(ray_origin, ray_direction, draft.plane)
        if point is None:
            log.error("[CsgDocumentEdit] cannot add draft point: ray does not hit active sketch plane")
            return DrawPointResult(False)
        draft.points.append(point)
        return DrawPointResult(True, point, "plane")

    hit = raycast_document(document, ray_origin, ray_direction)
    if hit is not None:
        draft.plane = sketch_plane_from_hit(hit)
        draft.points.append(hit.point)
        return DrawPointResult(True, hit.point, "solid")

    if fallback_point is None:
        log.error("[CsgDocumentEdit] cannot add draft point: ray hit no CSG solid and no fallback point was provided")
        return DrawPointResult(False)
    draft.plane = fallback_plane
    draft.points.append(fallback_point)
    return DrawPointResult(True, fallback_point, fallback_kind)


def close_draft_contour(
    document: ProceduralMeshDocument,
    draft: SketchDraft,
) -> DocumentEditResult:
    if len(draft.points) < 3:
        log.error(
            "[CsgDocumentEdit] cannot close contour: "
            f"need at least 3 points, got {len(draft.points)}"
        )
        return DocumentEditResult(False)

    plane = draft.plane
    if plane is None:
        plane = ProceduralPlane.from_points(draft.points)
    contour = document.add_contour_on_plane_from_points(draft.points[:], plane)
    if contour is None:
        return DocumentEditResult(False)
    sketch_id = document.find_sketch_id_for_contour(contour.id)
    draft.points = []
    draft.plane = None
    return DocumentEditResult(True, ("sketch", sketch_id), contour=contour)


def selected_sketch_id(
    document: ProceduralMeshDocument,
    selection: SelectionData | None,
) -> str:
    if selection is None:
        if document.items:
            return document.items[0].id
        return ""
    if selection[0] == "sketch":
        return selection[1]
    if selection[0] == "operation":
        operation = document.find_operation(selection[1])
        if operation is not None:
            return str(operation.params.get("source_sketch_id", ""))
    return ""


def add_extrude_for_selection(
    document: ProceduralMeshDocument,
    selection: SelectionData | None,
    height: float = 1.0,
) -> DocumentEditResult:
    sketch_id = selected_sketch_id(document, selection)
    if not sketch_id:
        log.error("[CsgDocumentEdit] cannot extrude: select a sketch")
        return DocumentEditResult(False)
    operation = document.add_extrude_operation_for_sketch(sketch_id, height=height)
    if operation is None:
        return DocumentEditResult(False)
    return DocumentEditResult(True, ("operation", operation.id), operation=operation)


def selected_operation_id(
    document: ProceduralMeshDocument,
    selection: SelectionData | None,
) -> str:
    if selection is not None and selection[0] == "operation":
        return selection[1]
    for operation in reversed(document.operations):
        if operation.enabled:
            return operation.id
    return ""


def add_boolean_for_selection(
    document: ProceduralMeshDocument,
    selection: SelectionData | None,
    kind: str,
) -> DocumentEditResult:
    input_ids = _boolean_input_ids_for_selection(document, selection)
    if len(input_ids) < 2:
        log.error("[CsgDocumentEdit] cannot add boolean operation: select an operation with a previous operation")
        return DocumentEditResult(False)
    operation = document.add_boolean_operation(kind, input_ids)
    if operation is None:
        return DocumentEditResult(False)
    return DocumentEditResult(True, ("operation", operation.id), operation=operation)


def set_extrude_vector(
    document: ProceduralMeshDocument,
    operation_id: str,
    vector: Vec3Data,
) -> bool:
    operation = document.find_operation(operation_id)
    if operation is None:
        log.error(f"[CsgDocumentEdit] cannot set extrude vector: operation not found '{operation_id}'")
        return False
    if operation.kind != "extrude":
        log.error(
            "[CsgDocumentEdit] cannot set extrude vector: "
            f"operation '{operation_id}' has kind '{operation.kind}'"
        )
        return False
    operation.params["vector"] = [float(vector[0]), float(vector[1]), float(vector[2])]
    return True


def set_sketch_plane(
    document: ProceduralMeshDocument,
    sketch_id: str,
    plane: ProceduralPlane,
) -> bool:
    sketch = document.find_sketch(sketch_id)
    if sketch is None:
        log.error(f"[CsgDocumentEdit] cannot set sketch plane: sketch not found '{sketch_id}'")
        return False
    normal_len = _vec_norm(_vec_cross(plane.x_axis, plane.y_axis))
    if normal_len < 1.0e-9:
        log.error(f"[CsgDocumentEdit] cannot set sketch plane: x_axis and y_axis are collinear sketch='{sketch_id}'")
        return False
    sketch.plane = plane
    return True


def _boolean_input_ids_for_selection(
    document: ProceduralMeshDocument,
    selection: SelectionData | None,
) -> list[str]:
    enabled_operations = [operation for operation in document.operations if operation.enabled]
    if len(enabled_operations) < 2:
        return []
    selected_id = selected_operation_id(document, selection)
    if not selected_id:
        return [enabled_operations[-2].id, enabled_operations[-1].id]

    selected_index = -1
    for index, operation in enumerate(enabled_operations):
        if operation.id == selected_id:
            selected_index = index
            break
    if selected_index < 0:
        log.error(f"[CsgDocumentEdit] cannot add boolean operation: selected operation not found '{selected_id}'")
        return []
    if selected_index == 0:
        log.error(f"[CsgDocumentEdit] cannot add boolean operation: selected operation has no previous input '{selected_id}'")
        return []
    return [enabled_operations[selected_index - 1].id, selected_id]


def _vec_cross(a: Vec3Data, b: Vec3Data) -> Vec3Data:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _vec_norm(value: Vec3Data) -> float:
    return (value[0] * value[0] + value[1] * value[1] + value[2] * value[2]) ** 0.5


__all__ = [
    "DocumentEditResult",
    "DrawPointResult",
    "SelectionData",
    "SketchDraft",
    "add_boolean_for_selection",
    "add_draft_point_from_ray",
    "add_extrude_for_selection",
    "clear_document",
    "close_draft_contour",
    "selected_sketch_id",
    "selected_operation_id",
    "set_extrude_vector",
    "set_sketch_plane",
    "start_sketch_draft",
]
