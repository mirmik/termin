"""Shared visual model for procedural CSG documents."""

from __future__ import annotations

from dataclasses import dataclass

from termin.csg.procedural_document import ProceduralMeshDocument

Vec3Data = tuple[float, float, float]
ColorData = tuple[float, float, float, float]

CONTOUR_COLOR: ColorData = (0.0, 0.95, 0.95, 1.0)
CONTOUR_SELECTED_COLOR: ColorData = (1.0, 1.0, 1.0, 1.0)
DRAFT_COLOR: ColorData = (1.0, 0.78, 0.12, 1.0)
POINT_COLOR: ColorData = (1.0, 1.0, 1.0, 1.0)


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


def _append_sketch(model: DocumentVisualModel, sketch, line_color: ColorData, point_color: ColorData) -> None:
    for contour in sketch.contours:
        points = sketch.contour_points(contour)
        model.polylines.append(VisualPolyline(points=points, color=line_color, closed=True))
        _append_points(model, points, point_color)


def _append_points(model: DocumentVisualModel, points: list[Vec3Data], color: ColorData) -> None:
    for point in points:
        model.points.append(VisualPoint(point=point, color=color))


def _find_contour(document: ProceduralMeshDocument, contour_id: str):
    for sketch in document.items:
        for contour in sketch.contours:
            if contour.id == contour_id:
                return (sketch, contour)
    return None


__all__ = [
    "CONTOUR_COLOR",
    "CONTOUR_SELECTED_COLOR",
    "DRAFT_COLOR",
    "POINT_COLOR",
    "DocumentVisualModel",
    "VisualPoint",
    "VisualPolyline",
    "build_document_visual_model",
]
