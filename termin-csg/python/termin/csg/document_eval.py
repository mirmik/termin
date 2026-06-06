"""Evaluate procedural CSG documents into renderable solids."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from tcbase import log
from tmesh import Mesh3

from termin.csg._csg_native import Solid, _extrude_pairs, from_mesh3, intersect, subtract, to_mesh3, unite
from termin.csg.procedural_document import BOOLEAN_OPERATION_KINDS, ProceduralMeshDocument, SketchItemDocument

Vec3Data = tuple[float, float, float]
PointTransform = Callable[[Vec3Data], Vec3Data]


@dataclass
class EvaluatedSolid:
    operation_id: str
    contour_id: str
    solid: Solid
    point_transform: PointTransform


def evaluate_document(document: ProceduralMeshDocument) -> list[EvaluatedSolid]:
    """Build enabled document operations into CSG solids.

    Solids are evaluated in their operation-local coordinates. The attached
    point transform maps those coordinates back into document-local 3D space,
    preserving sketch plane placement. Callers may apply additional scene or
    entity transforms after this point.
    """

    operation_results: dict[str, list[EvaluatedSolid]] = {}
    for operation in document.operations:
        if not operation.enabled:
            continue
        if operation.kind == "extrude":
            operation_results[operation.id] = _evaluate_extrude(document, operation)
        elif operation.kind in BOOLEAN_OPERATION_KINDS:
            operation_results[operation.id] = _evaluate_boolean(operation, operation_results)
        else:
            log.error(
                "[ProceduralMeshDocument] cannot evaluate operation: "
                f"unknown kind '{operation.kind}' operation='{operation.id}'"
            )

    consumed_operation_ids = document.used_input_operation_ids()
    results: list[EvaluatedSolid] = []
    for operation in document.operations:
        if not operation.enabled or operation.id in consumed_operation_ids:
            continue
        results.extend(operation_results.get(operation.id, []))
    return results


def _evaluate_extrude(document: ProceduralMeshDocument, operation) -> list[EvaluatedSolid]:
    source_sketch_id = str(operation.params.get("source_sketch_id", ""))
    sketch = document.find_sketch(source_sketch_id)
    if sketch is None:
        log.error(
            "[ProceduralMeshDocument] cannot evaluate extrude operation: "
            f"sketch not found '{source_sketch_id}'"
        )
        return []

    extrusion_vector = extrude_vector_for_operation(sketch, operation)
    if _norm(extrusion_vector) < 1.0e-9:
        log.error(
            "[ProceduralMeshDocument] cannot evaluate extrude operation: "
            f"zero extrusion vector operation='{operation.id}'"
        )
        return []

    extrusion_length = _norm(extrusion_vector)
    point_transform = sketch_extrude_point_transform(sketch, extrusion_vector, extrusion_length)
    results: list[EvaluatedSolid] = []
    for contour in sketch.contours:
        if contour.id not in operation.inputs:
            continue
        try:
            solid = _extrude_pairs(contour.points, extrusion_length, [])
        except Exception as e:
            log.error(
                "[ProceduralMeshDocument] failed to evaluate extrude "
                f"operation='{operation.id}' contour='{contour.id}': {e}"
            )
            continue
        results.append(
            EvaluatedSolid(
                operation_id=operation.id,
                contour_id=contour.id,
                solid=solid,
                point_transform=point_transform,
            )
        )
    return results


def _evaluate_boolean(
    operation,
    operation_results: dict[str, list[EvaluatedSolid]],
) -> list[EvaluatedSolid]:
    operands: list[Solid] = []
    for input_id in operation.inputs:
        evaluated_items = operation_results.get(input_id)
        if evaluated_items is None:
            log.error(
                "[ProceduralMeshDocument] cannot evaluate boolean operation: "
                f"input operation not evaluated operation='{operation.id}' input='{input_id}'"
            )
            return []
        operand = _combine_evaluated_solids(evaluated_items, operation.id, input_id)
        if operand is None:
            return []
        operands.append(operand)

    if len(operands) < 2:
        log.error(
            "[ProceduralMeshDocument] cannot evaluate boolean operation: "
            f"need at least 2 operands operation='{operation.id}'"
        )
        return []

    try:
        result = _fold_boolean(operation.kind, operands)
    except Exception as e:
        log.error(
            "[ProceduralMeshDocument] failed to evaluate boolean "
            f"operation='{operation.id}' kind='{operation.kind}': {e}"
        )
        return []

    if result.status != "No Error":
        log.error(
            "[ProceduralMeshDocument] boolean operation returned invalid solid "
            f"operation='{operation.id}' kind='{operation.kind}' status='{result.status}'"
        )
    return [
        EvaluatedSolid(
            operation_id=operation.id,
            contour_id="",
            solid=result,
            point_transform=_identity_point_transform,
        )
    ]


def _combine_evaluated_solids(
    evaluated_items: list[EvaluatedSolid],
    operation_id: str,
    input_id: str,
) -> Solid | None:
    if not evaluated_items:
        log.error(
            "[ProceduralMeshDocument] cannot evaluate boolean operation: "
            f"input operation produced no solids operation='{operation_id}' input='{input_id}'"
        )
        return None

    solids: list[Solid] = []
    for evaluated in evaluated_items:
        solid = _evaluated_solid_in_document_space(evaluated)
        if solid is None:
            return None
        solids.append(solid)

    result = solids[0]
    for solid in solids[1:]:
        result = unite(result, solid)
    return result


def _evaluated_solid_in_document_space(evaluated: EvaluatedSolid) -> Solid | None:
    try:
        mesh = to_mesh3(evaluated.solid, "csg-document-space", "", False)
        vertices = np.asarray(mesh.vertices, dtype=np.float32).reshape(-1, 3)
        transformed = np.array(
            [evaluated.point_transform((float(v[0]), float(v[1]), float(v[2]))) for v in vertices],
            dtype=np.float32,
        )
        triangles = np.asarray(mesh.triangles, dtype=np.uint32).reshape(-1, 3)
        return from_mesh3(
            Mesh3(
                name="csg-document-space",
                vertices=np.ascontiguousarray(transformed, dtype=np.float32),
                triangles=np.ascontiguousarray(triangles, dtype=np.uint32),
            )
        )
    except Exception as e:
        log.error(
            "[ProceduralMeshDocument] failed to transform evaluated solid into document space "
            f"operation='{evaluated.operation_id}' contour='{evaluated.contour_id}': {e}"
        )
        return None


def _fold_boolean(kind: str, operands: list[Solid]) -> Solid:
    result = operands[0]
    if kind == "union":
        for operand in operands[1:]:
            result = unite(result, operand)
        return result
    if kind == "subtract":
        for operand in operands[1:]:
            result = subtract(result, operand)
        return result
    if kind == "intersect":
        for operand in operands[1:]:
            result = intersect(result, operand)
        return result
    raise ValueError(f"unsupported boolean operation kind '{kind}'")


def _identity_point_transform(point: Vec3Data) -> Vec3Data:
    return point


def sketch_point_transform(sketch: SketchItemDocument):
    """Return operation-local to document-local transform for a sketch plane."""
    return sketch_extrude_point_transform(sketch, sketch.plane.normal, 1.0)


def extrude_vector_for_operation(sketch: SketchItemDocument, operation) -> Vec3Data:
    vector = operation.params.get("vector")
    if vector is not None:
        try:
            return (float(vector[0]), float(vector[1]), float(vector[2]))
        except Exception as e:
            log.error(
                "[ProceduralMeshDocument] invalid extrude vector "
                f"operation='{operation.id}': {e}"
            )
            return (0.0, 0.0, 0.0)

    height = float(operation.params.get("height", 1.0))
    return (
        sketch.plane.normal[0] * height,
        sketch.plane.normal[1] * height,
        sketch.plane.normal[2] * height,
    )


def sketch_extrude_point_transform(
    sketch: SketchItemDocument,
    extrusion_vector: Vec3Data,
    extrusion_length: float,
):
    """Return local XY + unit-Z extrude coordinates to document-local transform."""

    origin = sketch.plane.origin
    x_axis = sketch.plane.x_axis
    y_axis = sketch.plane.y_axis
    z_scale = 1.0 / extrusion_length

    def transform(point: Vec3Data) -> Vec3Data:
        z = point[2] * z_scale
        return (
            origin[0] + x_axis[0] * point[0] + y_axis[0] * point[1] + extrusion_vector[0] * z,
            origin[1] + x_axis[1] * point[0] + y_axis[1] * point[1] + extrusion_vector[1] * z,
            origin[2] + x_axis[2] * point[0] + y_axis[2] * point[1] + extrusion_vector[2] * z,
        )

    return transform


def _norm(value: Vec3Data) -> float:
    return (value[0] * value[0] + value[1] * value[1] + value[2] * value[2]) ** 0.5


__all__ = [
    "EvaluatedSolid",
    "evaluate_document",
    "extrude_vector_for_operation",
    "sketch_extrude_point_transform",
    "sketch_point_transform",
]
