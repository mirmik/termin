"""Shared interaction helpers for dragging sketch contour/path points."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from tcbase import log

from termin.csg.document_raycast import ray_plane_intersection
from termin.csg.procedural_document import ProceduralMeshDocument, Vec2Data, Vec3Data


DEFAULT_SKETCH_POINT_HIT_RADIUS_PX = 14.0
ProjectPoint = Callable[[Vec3Data], tuple[float, float] | None]


@dataclass(frozen=True)
class SketchPointDrag:
    kind: str
    item_id: str
    point_index: int


def pick_selected_sketch_point(
    document: ProceduralMeshDocument,
    selection: tuple[str, str] | None,
    project_point: ProjectPoint,
    x: float,
    y: float,
    *,
    hit_radius_px: float = DEFAULT_SKETCH_POINT_HIT_RADIUS_PX,
) -> SketchPointDrag | None:
    selected = selected_sketch_point_source(document, selection)
    if selected is None:
        return None
    kind, item_id, points = selected
    best_index = -1
    best_distance_sq = hit_radius_px * hit_radius_px
    for index, point in enumerate(points):
        screen_point = project_point(point)
        if screen_point is None:
            continue
        dx = screen_point[0] - float(x)
        dy = screen_point[1] - float(y)
        distance_sq = dx * dx + dy * dy
        if distance_sq <= best_distance_sq:
            best_distance_sq = distance_sq
            best_index = index
    if best_index < 0:
        return None
    return SketchPointDrag(kind, item_id, best_index)


def drag_point_to_ray(
    document: ProceduralMeshDocument,
    drag: SketchPointDrag,
    ray_origin: Vec3Data,
    ray_direction: Vec3Data,
) -> Vec2Data | None:
    point_ref = sketch_point_ref_by_drag(document, drag)
    if point_ref is None:
        log.error(
            "[CsgSketchPointInteraction] cannot drag sketch point: "
            f"item not found kind='{drag.kind}' id='{drag.item_id}'"
        )
        return None
    sketch = point_ref[0]
    point = ray_plane_intersection(ray_origin, ray_direction, sketch.plane)
    if point is None:
        log.error(
            "[CsgSketchPointInteraction] cannot drag sketch point: "
            f"ray does not hit sketch plane kind='{drag.kind}' id='{drag.item_id}' index={drag.point_index}"
        )
        return None
    return sketch.plane.project(point)


def selected_sketch_point_source(
    document: ProceduralMeshDocument,
    selection: tuple[str, str] | None,
):
    if selection is None:
        return None
    kind, item_id = selection
    if kind == "contour":
        contour_ref = document.find_contour_ref(item_id)
        if contour_ref is None:
            return None
        sketch, contour = contour_ref
        return ("contour", contour.id, sketch.contour_points(contour))
    if kind == "path":
        path_ref = document.find_path_ref(item_id)
        if path_ref is None:
            return None
        sketch, path = path_ref
        return ("path", path.id, sketch.path_points(path))
    return None


def sketch_point_ref_by_drag(document: ProceduralMeshDocument, drag: SketchPointDrag):
    if drag.kind == "contour":
        return document.find_contour_ref(drag.item_id)
    if drag.kind == "path":
        return document.find_path_ref(drag.item_id)
    return None


__all__ = [
    "DEFAULT_SKETCH_POINT_HIT_RADIUS_PX",
    "ProjectPoint",
    "SketchPointDrag",
    "drag_point_to_ray",
    "pick_selected_sketch_point",
    "selected_sketch_point_source",
    "sketch_point_ref_by_drag",
]
