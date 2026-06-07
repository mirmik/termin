"""Shared visual model for procedural CSG documents."""

from __future__ import annotations

from dataclasses import dataclass

from termin.csg.procedural_document import OPERATION_KIND_WALL, ProceduralMeshDocument
from termin.csg.wall_height_offsets import wall_effective_corner_heights

Vec3Data = tuple[float, float, float]
ColorData = tuple[float, float, float, float]

CONTOUR_COLOR: ColorData = (0.0, 0.95, 0.95, 1.0)
CONTOUR_SELECTED_COLOR: ColorData = (1.0, 1.0, 1.0, 1.0)
PATH_COLOR: ColorData = (0.95, 0.42, 0.18, 1.0)
PATH_SELECTED_COLOR: ColorData = (1.0, 0.86, 0.38, 1.0)
DRAFT_COLOR: ColorData = (1.0, 0.78, 0.12, 1.0)
POINT_COLOR: ColorData = (1.0, 1.0, 1.0, 1.0)
WALL_HEIGHT_COLOR: ColorData = (0.36, 0.72, 1.0, 1.0)


@dataclass
class VisualPolyline:
    points: list[Vec3Data]
    color: ColorData
    closed: bool = False
    depth_test: bool = False


@dataclass
class VisualPoint:
    point: Vec3Data
    color: ColorData
    radius: float = 0.055
    depth_test: bool = False


@dataclass
class DocumentVisualModel:
    polylines: list[VisualPolyline]
    points: list[VisualPoint]


def build_document_visual_model(
    document: ProceduralMeshDocument,
    draft_points: list[Vec3Data] | None = None,
    selected_node_data: tuple[str, str] | None = None,
) -> DocumentVisualModel:
    """Build the editor/CAD debug visual model for a procedural document."""

    model = DocumentVisualModel(polylines=[], points=[])
    used_sketch_ids = document.used_source_sketch_ids()
    for item in document.items:
        if item.id not in used_sketch_ids:
            _append_sketch(model, item, CONTOUR_COLOR, POINT_COLOR)

    _append_selected_item(model, document, selected_node_data)

    if draft_points:
        points = draft_points[:]
        model.polylines.append(VisualPolyline(points=points, color=DRAFT_COLOR, closed=False))
        _append_points(model, points, DRAFT_COLOR)
    return model


def _append_selected_item(
    model: DocumentVisualModel,
    document: ProceduralMeshDocument,
    selected_node_data: tuple[str, str] | None,
) -> None:
    if selected_node_data is None:
        return
    kind = selected_node_data[0]
    item_id = selected_node_data[1]
    if kind == "sketch":
        sketch = document.find_sketch(item_id)
        if sketch is not None:
            _append_sketch(model, sketch, CONTOUR_SELECTED_COLOR, CONTOUR_SELECTED_COLOR)
        return
    if kind == "contour":
        contour_ref = _find_contour(document, item_id)
        if contour_ref is None:
            return
        sketch, contour = contour_ref
        points = sketch.contour_points(contour)
        model.polylines.append(
            VisualPolyline(
                points=points,
                color=CONTOUR_SELECTED_COLOR,
                closed=True,
                depth_test=False,
            )
        )
        _append_points(model, points, CONTOUR_SELECTED_COLOR)
    if kind == "path":
        path_ref = _find_path(document, item_id)
        if path_ref is None:
            return
        sketch, path = path_ref
        points = sketch.path_points(path)
        model.polylines.append(
            VisualPolyline(
                points=points,
                color=PATH_SELECTED_COLOR,
                closed=path.closed,
                depth_test=False,
            )
        )
        _append_points(model, points, PATH_SELECTED_COLOR)
        return
    if kind == "operation":
        operation = document.find_operation(item_id)
        if operation is not None and operation.kind == OPERATION_KIND_WALL:
            _append_wall_source_geometry(model, document, operation)
            _append_wall_height_handles(model, document, operation)


def _append_sketch(model: DocumentVisualModel, sketch, line_color: ColorData, point_color: ColorData) -> None:
    for contour in sketch.contours:
        points = sketch.contour_points(contour)
        model.polylines.append(VisualPolyline(points=points, color=line_color, closed=True))
        _append_points(model, points, point_color)
    for path in sketch.paths:
        points = sketch.path_points(path)
        model.polylines.append(VisualPolyline(points=points, color=PATH_COLOR, closed=path.closed))
        _append_points(model, points, PATH_COLOR)


def _append_points(model: DocumentVisualModel, points: list[Vec3Data], color: ColorData) -> None:
    for point in points:
        model.points.append(VisualPoint(point=point, color=color))


def _append_wall_source_geometry(model: DocumentVisualModel, document: ProceduralMeshDocument, operation) -> None:
    source_sketch_id = str(operation.params.get("source_sketch_id", ""))
    sketch = document.find_sketch(source_sketch_id)
    if sketch is None:
        return
    input_ids = set(operation.inputs)
    for path in sketch.paths:
        if path.id not in input_ids:
            continue
        points = sketch.path_points(path)
        model.polylines.append(
            VisualPolyline(
                points=points,
                color=PATH_SELECTED_COLOR,
                closed=path.closed,
                depth_test=False,
            )
        )
        _append_points(model, points, PATH_SELECTED_COLOR)
    for contour in sketch.outer_contours():
        if contour.id not in input_ids:
            continue
        if sketch.hole_contours_for_outer(contour.id):
            continue
        points = sketch.contour_points(contour)
        model.polylines.append(
            VisualPolyline(
                points=points,
                color=CONTOUR_SELECTED_COLOR,
                closed=True,
                depth_test=False,
            )
        )
        _append_points(model, points, CONTOUR_SELECTED_COLOR)


def _append_wall_height_handles(model: DocumentVisualModel, document: ProceduralMeshDocument, operation) -> None:
    source_sketch_id = str(operation.params.get("source_sketch_id", ""))
    sketch = document.find_sketch(source_sketch_id)
    if sketch is None:
        return
    base_height = _param_float(operation.params, "height", 3.0)
    normal = sketch.plane.normal
    input_ids = set(operation.inputs)
    for path in sketch.paths:
        if path.id not in input_ids:
            continue
        base_points = sketch.path_points(path)
        _append_wall_source_height_handles(model, operation, path.id, base_points, base_height, normal)
    for contour in sketch.outer_contours():
        if contour.id not in input_ids:
            continue
        if sketch.hole_contours_for_outer(contour.id):
            continue
        base_points = sketch.contour_points(contour)
        _append_wall_source_height_handles(model, operation, contour.id, base_points, base_height, normal)


def _append_wall_source_height_handles(
    model: DocumentVisualModel,
    operation,
    source_id: str,
    base_points: list[Vec3Data],
    base_height: float,
    normal: Vec3Data,
) -> None:
    heights = wall_effective_corner_heights(
        operation.params,
        source_id,
        len(base_points),
        base_height,
        operation_id=operation.id,
    )
    for index, base_point in enumerate(base_points):
        height = heights[index]
        top_point = (
            base_point[0] + normal[0] * height,
            base_point[1] + normal[1] * height,
            base_point[2] + normal[2] * height,
        )
        model.polylines.append(VisualPolyline(points=[base_point, top_point], color=WALL_HEIGHT_COLOR, closed=False))
        model.points.append(VisualPoint(point=top_point, color=WALL_HEIGHT_COLOR, radius=0.07, depth_test=False))


def _param_float(params: dict, key: str, default: float) -> float:
    try:
        return float(params.get(key, default))
    except Exception:
        return float(default)


def _find_contour(document: ProceduralMeshDocument, contour_id: str):
    for sketch in document.items:
        for contour in sketch.contours:
            if contour.id == contour_id:
                return (sketch, contour)
    return None


def _find_path(document: ProceduralMeshDocument, path_id: str):
    for sketch in document.items:
        for path in sketch.paths:
            if path.id == path_id:
                return (sketch, path)
    return None


__all__ = [
    "CONTOUR_COLOR",
    "CONTOUR_SELECTED_COLOR",
    "DRAFT_COLOR",
    "PATH_COLOR",
    "PATH_SELECTED_COLOR",
    "POINT_COLOR",
    "WALL_HEIGHT_COLOR",
    "DocumentVisualModel",
    "VisualPoint",
    "VisualPolyline",
    "build_document_visual_model",
]
