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

    height = float(operation.params.get("height", 1.0))
    point_transform = sketch_point_transform(sketch)
    results: list[EvaluatedSolid] = []
    for contour in sketch.contours:
        if contour.id not in operation.inputs:
            continue
        try:
            solid = _extrude_pairs(contour.points, height, [])
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

    origin = sketch.plane.origin
    x_axis = sketch.plane.x_axis
    y_axis = sketch.plane.y_axis
    normal = sketch.plane.normal

    def transform(point: Vec3Data) -> Vec3Data:
        return (
            origin[0] + x_axis[0] * point[0] + y_axis[0] * point[1] + normal[0] * point[2],
            origin[1] + x_axis[1] * point[0] + y_axis[1] * point[1] + normal[1] * point[2],
            origin[2] + x_axis[2] * point[0] + y_axis[2] * point[1] + normal[2] * point[2],
        )

    return transform


__all__ = [
    "EvaluatedSolid",
    "evaluate_document",
    "sketch_point_transform",
]
