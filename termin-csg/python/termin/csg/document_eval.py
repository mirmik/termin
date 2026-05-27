"""Evaluate procedural CSG documents into renderable solids."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from tcbase import log

from termin.csg._csg_native import Solid, _extrude_pairs
from termin.csg.procedural_document import ProceduralMeshDocument, SketchItemDocument

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

    results: list[EvaluatedSolid] = []
    for operation in document.operations:
        if not operation.enabled:
            continue
        if operation.kind == "extrude":
            results.extend(_evaluate_extrude(document, operation))
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
