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


__all__ = [
    "DocumentEditResult",
    "DrawPointResult",
    "SelectionData",
    "SketchDraft",
    "add_draft_point_from_ray",
    "add_extrude_for_selection",
    "clear_document",
    "close_draft_contour",
    "selected_sketch_id",
    "start_sketch_draft",
]
