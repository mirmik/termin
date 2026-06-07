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
    BOOLEAN_OPERATION_KINDS,
    CONTOUR_ROLE_OUTER,
    PRIMITIVE_OPERATION_KIND,
    ContourDocument,
    OperationDocument,
    ProceduralMeshDocument,
    ProceduralPlane,
    SketchPathDocument,
)
from termin.csg.wall_height_offsets import set_wall_corner_height_offset

Vec2Data = tuple[float, float]
Vec3Data = tuple[float, float, float]
SelectionData = tuple[str, str]


@dataclass
class SketchDraft:
    points: list[Vec3Data] = field(default_factory=list)
    plane: ProceduralPlane | None = None
    sketch_id: str = ""
    contour_role: str = CONTOUR_ROLE_OUTER
    parent_contour_id: str | None = None
    purpose: str = "contour"


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
    path: SketchPathDocument | None = None


def start_sketch_draft(
    sketch_id: str = "",
    plane: ProceduralPlane | None = None,
    contour_role: str = CONTOUR_ROLE_OUTER,
    parent_contour_id: str | None = None,
    purpose: str = "contour",
) -> SketchDraft:
    return SketchDraft(
        plane=plane,
        sketch_id=str(sketch_id),
        contour_role=str(contour_role),
        parent_contour_id=parent_contour_id,
        purpose=str(purpose),
    )


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
    if not draft.points and draft.plane is not None:
        point = ray_plane_intersection(ray_origin, ray_direction, draft.plane)
        if point is None:
            log.error("[CsgDocumentEdit] cannot add draft point: ray does not hit active sketch plane")
            return DrawPointResult(False)
        draft.points.append(point)
        return DrawPointResult(True, point, "plane")

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
    if draft.sketch_id:
        contour = document.add_contour_to_sketch_from_points(
            draft.sketch_id,
            draft.points[:],
            role=draft.contour_role,
            parent_contour_id=draft.parent_contour_id,
        )
        selection = ("contour", contour.id) if contour is not None else None
    else:
        contour = document.add_contour_on_plane_from_points(draft.points[:], plane)
        sketch_id = document.find_sketch_id_for_contour(contour.id) if contour is not None else ""
        selection = ("sketch", sketch_id) if sketch_id else None
    if contour is None:
        return DocumentEditResult(False)
    draft.points = []
    draft.plane = None
    draft.sketch_id = ""
    draft.parent_contour_id = None
    draft.contour_role = CONTOUR_ROLE_OUTER
    draft.purpose = "contour"
    return DocumentEditResult(True, selection, contour=contour)


def finish_draft_path(
    document: ProceduralMeshDocument,
    draft: SketchDraft,
    purpose: str = "wall",
) -> DocumentEditResult:
    if len(draft.points) < 2:
        log.error(
            "[CsgDocumentEdit] cannot finish path: "
            f"need at least 2 points, got {len(draft.points)}"
        )
        return DocumentEditResult(False)

    plane = draft.plane
    if plane is None:
        plane = ProceduralPlane.from_points(draft.points)
    path_purpose = str(purpose or draft.purpose or "wall")
    if draft.sketch_id:
        path = document.add_path_to_sketch_from_points(
            draft.sketch_id,
            draft.points[:],
            purpose=path_purpose,
            closed=False,
        )
        selection = ("path", path.id) if path is not None else None
    else:
        path = document.add_path_on_plane_from_points(
            draft.points[:],
            plane,
            purpose=path_purpose,
            closed=False,
        )
        selection = ("path", path.id) if path is not None else None
    if path is None:
        return DocumentEditResult(False)
    draft.points = []
    draft.plane = None
    draft.sketch_id = ""
    draft.parent_contour_id = None
    draft.contour_role = CONTOUR_ROLE_OUTER
    draft.purpose = "contour"
    return DocumentEditResult(True, selection, path=path)


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
    if selection[0] == "contour":
        return document.find_sketch_id_for_contour(selection[1])
    if selection[0] == "path":
        return document.find_sketch_id_for_path(selection[1])
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
    if selection is None or selection[0] != "sketch":
        log.error("[CsgDocumentEdit] cannot extrude: select a sketch")
        return DocumentEditResult(False)
    sketch_id = selection[1]
    operation = document.add_extrude_operation_for_sketch(sketch_id, height=height)
    if operation is None:
        return DocumentEditResult(False)
    return DocumentEditResult(True, ("operation", operation.id), operation=operation)


def add_wall_for_selection(
    document: ProceduralMeshDocument,
    selection: SelectionData | None,
    height: float = 3.0,
    thickness: float = 0.2,
    alignment: str = "center",
) -> DocumentEditResult:
    if selection is None or selection[0] != "sketch":
        log.error("[CsgDocumentEdit] cannot create wall: select a sketch")
        return DocumentEditResult(False)
    operation = document.add_wall_operation_for_sketch(
        selection[1],
        height=height,
        thickness=thickness,
        alignment=alignment,
    )
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


def add_boolean_input(
    document: ProceduralMeshDocument,
    boolean_operation_id: str,
    input_operation_id: str,
    insert_index: int | None = None,
) -> bool:
    boolean_operation = _find_boolean_operation(document, boolean_operation_id, "add boolean input")
    if boolean_operation is None:
        return False
    input_operation = document.find_operation(input_operation_id)
    if input_operation is None:
        log.error(f"[CsgDocumentEdit] cannot add boolean input: operation not found '{input_operation_id}'")
        return False
    if boolean_operation.id == input_operation.id:
        log.error(f"[CsgDocumentEdit] cannot add boolean input: operation cannot contain itself '{input_operation_id}'")
        return False
    if input_operation.id in boolean_operation.inputs:
        log.error(
            "[CsgDocumentEdit] cannot add boolean input: "
            f"duplicate input operation='{boolean_operation.id}' input='{input_operation.id}'"
        )
        return False
    if _operation_depends_on(document, input_operation.id, boolean_operation.id, set()):
        log.error(
            "[CsgDocumentEdit] cannot add boolean input: "
            f"cycle detected operation='{boolean_operation.id}' input='{input_operation.id}'"
        )
        return False

    index = _clamped_insert_index(insert_index, len(boolean_operation.inputs))
    boolean_operation.inputs.insert(index, input_operation.id)
    return True


def remove_boolean_input(
    document: ProceduralMeshDocument,
    boolean_operation_id: str,
    input_operation_id: str,
) -> bool:
    boolean_operation = _find_boolean_operation(document, boolean_operation_id, "remove boolean input")
    if boolean_operation is None:
        return False
    if input_operation_id not in boolean_operation.inputs:
        log.error(
            "[CsgDocumentEdit] cannot remove boolean input: "
            f"input not found operation='{boolean_operation.id}' input='{input_operation_id}'"
        )
        return False
    if len(boolean_operation.inputs) <= 2:
        log.error(
            "[CsgDocumentEdit] cannot remove boolean input: "
            f"boolean operation needs at least 2 inputs operation='{boolean_operation.id}'"
        )
        return False
    boolean_operation.inputs.remove(input_operation_id)
    return True


def move_boolean_input(
    document: ProceduralMeshDocument,
    source_boolean_operation_id: str,
    target_boolean_operation_id: str,
    input_operation_id: str,
    insert_index: int | None = None,
) -> bool:
    source_operation = _find_boolean_operation(document, source_boolean_operation_id, "move boolean input")
    target_operation = _find_boolean_operation(document, target_boolean_operation_id, "move boolean input")
    if source_operation is None or target_operation is None:
        return False
    if input_operation_id not in source_operation.inputs:
        log.error(
            "[CsgDocumentEdit] cannot move boolean input: "
            f"input not found operation='{source_operation.id}' input='{input_operation_id}'"
        )
        return False
    if source_operation.id != target_operation.id and len(source_operation.inputs) <= 2:
        log.error(
            "[CsgDocumentEdit] cannot move boolean input: "
            f"source boolean operation needs at least 2 inputs operation='{source_operation.id}'"
        )
        return False

    source_index = source_operation.inputs.index(input_operation_id)
    index = _clamped_insert_index(insert_index, len(target_operation.inputs))
    source_operation.inputs.pop(source_index)
    if source_operation.id == target_operation.id:
        if index > source_index:
            index -= 1
        source_operation.inputs.insert(index, input_operation_id)
        return True

    if input_operation_id in target_operation.inputs:
        source_operation.inputs.insert(source_index, input_operation_id)
        log.error(
            "[CsgDocumentEdit] cannot move boolean input: "
            f"duplicate input operation='{target_operation.id}' input='{input_operation_id}'"
        )
        return False
    if _operation_depends_on(document, input_operation_id, target_operation.id, set()):
        source_operation.inputs.insert(source_index, input_operation_id)
        log.error(
            "[CsgDocumentEdit] cannot move boolean input: "
            f"cycle detected operation='{target_operation.id}' input='{input_operation_id}'"
        )
        return False
    target_operation.inputs.insert(index, input_operation_id)
    return True


def add_primitive_operation(
    document: ProceduralMeshDocument,
    kind: str,
) -> DocumentEditResult:
    operation = document.add_primitive_operation(kind)
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


def set_primitive_params(
    document: ProceduralMeshDocument,
    operation_id: str,
    params: dict,
) -> bool:
    operation = document.find_operation(operation_id)
    if operation is None:
        log.error(f"[CsgDocumentEdit] cannot set primitive params: operation not found '{operation_id}'")
        return False
    if operation.kind != PRIMITIVE_OPERATION_KIND:
        log.error(
            "[CsgDocumentEdit] cannot set primitive params: "
            f"operation '{operation_id}' has kind '{operation.kind}'"
        )
        return False
    operation.params.update(dict(params))
    return True


def set_wall_params(
    document: ProceduralMeshDocument,
    operation_id: str,
    height: float,
    thickness: float,
    alignment: str,
) -> bool:
    operation = document.find_operation(operation_id)
    if operation is None:
        log.error(f"[CsgDocumentEdit] cannot set wall params: operation not found '{operation_id}'")
        return False
    if operation.kind != "wall":
        log.error(
            "[CsgDocumentEdit] cannot set wall params: "
            f"operation '{operation_id}' has kind '{operation.kind}'"
        )
        return False
    if float(height) <= 0.0 or float(thickness) <= 0.0:
        log.error(
            "[CsgDocumentEdit] cannot set wall params: "
            f"height and thickness must be positive operation='{operation_id}'"
        )
        return False
    alignment_value = str(alignment)
    if alignment_value not in {"center", "left", "right"}:
        log.error(
            "[CsgDocumentEdit] cannot set wall params: "
            f"invalid alignment '{alignment}' operation='{operation_id}'"
        )
        return False
    operation.params["height"] = float(height)
    operation.params["thickness"] = float(thickness)
    operation.params["alignment"] = alignment_value
    return True


def set_wall_corner_offset(
    document: ProceduralMeshDocument,
    operation_id: str,
    source_id: str,
    point_index: int,
    offset: float,
) -> bool:
    return set_wall_corner_height_offset(document, operation_id, source_id, point_index, offset)


def set_operation_transform(
    document: ProceduralMeshDocument,
    operation_id: str,
    center: Vec3Data,
    rotation: Vec3Data,
) -> bool:
    operation = document.find_operation(operation_id)
    if operation is None:
        log.error(f"[CsgDocumentEdit] cannot set operation transform: operation not found '{operation_id}'")
        return False
    operation.params["center"] = [float(center[0]), float(center[1]), float(center[2])]
    operation.params["rotation"] = [float(rotation[0]), float(rotation[1]), float(rotation[2])]
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


def set_contour_point(
    document: ProceduralMeshDocument,
    contour_id: str,
    point_index: int,
    point: Vec2Data,
) -> bool:
    contour = _find_contour(document, contour_id)
    if contour is None:
        log.error(f"[CsgDocumentEdit] cannot set contour point: contour not found '{contour_id}'")
        return False
    index = int(point_index)
    if index < 0 or index >= len(contour.points):
        log.error(
            "[CsgDocumentEdit] cannot set contour point: "
            f"index out of range contour='{contour_id}' index={index} points={len(contour.points)}"
        )
        return False
    contour.points[index] = (float(point[0]), float(point[1]))
    return True


def set_path_point(
    document: ProceduralMeshDocument,
    path_id: str,
    point_index: int,
    point: Vec2Data,
) -> bool:
    path_ref = document.find_path_ref(path_id)
    if path_ref is None:
        log.error(f"[CsgDocumentEdit] cannot set path point: path not found '{path_id}'")
        return False
    _sketch, path = path_ref
    index = int(point_index)
    if index < 0 or index >= len(path.points):
        log.error(
            "[CsgDocumentEdit] cannot set path point: "
            f"index out of range path='{path_id}' index={index} points={len(path.points)}"
        )
        return False
    path.points[index] = (float(point[0]), float(point[1]))
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


def _find_boolean_operation(
    document: ProceduralMeshDocument,
    operation_id: str,
    action: str,
) -> OperationDocument | None:
    operation = document.find_operation(operation_id)
    if operation is None:
        log.error(f"[CsgDocumentEdit] cannot {action}: operation not found '{operation_id}'")
        return None
    if operation.kind not in BOOLEAN_OPERATION_KINDS:
        log.error(
            f"[CsgDocumentEdit] cannot {action}: "
            f"operation '{operation_id}' has kind '{operation.kind}'"
        )
        return None
    return operation


def _operation_depends_on(
    document: ProceduralMeshDocument,
    operation_id: str,
    target_operation_id: str,
    visited: set[str],
) -> bool:
    if operation_id == target_operation_id:
        return True
    if operation_id in visited:
        return False
    visited.add(operation_id)
    operation = document.find_operation(operation_id)
    if operation is None:
        return False
    if operation.kind not in BOOLEAN_OPERATION_KINDS:
        return False
    for input_id in operation.inputs:
        if _operation_depends_on(document, input_id, target_operation_id, visited):
            return True
    return False


def _clamped_insert_index(index: int | None, length: int) -> int:
    if index is None:
        return length
    return max(0, min(int(index), length))


def _find_contour(document: ProceduralMeshDocument, contour_id: str) -> ContourDocument | None:
    for sketch in document.items:
        for contour in sketch.contours:
            if contour.id == contour_id:
                return contour
    return None


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
    "add_boolean_input",
    "add_boolean_for_selection",
    "add_draft_point_from_ray",
    "add_extrude_for_selection",
    "add_primitive_operation",
    "add_wall_for_selection",
    "clear_document",
    "close_draft_contour",
    "finish_draft_path",
    "selected_sketch_id",
    "selected_operation_id",
    "move_boolean_input",
    "remove_boolean_input",
    "set_contour_point",
    "set_extrude_vector",
    "set_operation_transform",
    "set_path_point",
    "set_primitive_params",
    "set_wall_corner_offset",
    "set_wall_params",
    "set_sketch_plane",
    "start_sketch_draft",
]
