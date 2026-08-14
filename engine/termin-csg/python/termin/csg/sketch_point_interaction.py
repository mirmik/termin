"""Shared interaction helpers for dragging sketch contour/path points."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from tcbase import log

from termin.csg.document_raycast import ray_plane_intersection
from termin.csg.procedural_document import OPERATION_KIND_WALL, ProceduralMeshDocument, Vec2Data, Vec3Data
from termin.csg.wall_height_offsets import MIN_WALL_CORNER_HEIGHT, wall_effective_corner_heights


DEFAULT_SKETCH_POINT_HIT_RADIUS_PX = 14.0
ProjectPoint = Callable[[Vec3Data], tuple[float, float] | None]


@dataclass(frozen=True)
class SketchPointDrag:
    kind: str
    item_id: str
    point_index: int


@dataclass(frozen=True)
class WallHeightDrag:
    operation_id: str
    source_kind: str
    source_id: str
    point_index: int
    base_point: Vec3Data
    normal: Vec3Data
    base_height: float
    effective_height: float


def pick_selected_sketch_point(
    document: ProceduralMeshDocument,
    selection: tuple[str, str] | None,
    project_point: ProjectPoint,
    x: float,
    y: float,
    *,
    hit_radius_px: float = DEFAULT_SKETCH_POINT_HIT_RADIUS_PX,
) -> SketchPointDrag | None:
    sources = selected_sketch_point_sources(document, selection)
    if not sources:
        return None
    best_drag: SketchPointDrag | None = None
    best_distance_sq = hit_radius_px * hit_radius_px
    for kind, item_id, points in sources:
        for index, point in enumerate(points):
            screen_point = project_point(point)
            if screen_point is None:
                continue
            dx = screen_point[0] - float(x)
            dy = screen_point[1] - float(y)
            distance_sq = dx * dx + dy * dy
            if distance_sq <= best_distance_sq:
                best_distance_sq = distance_sq
                best_drag = SketchPointDrag(kind, item_id, index)
    return best_drag


def pick_selected_wall_height_point(
    document: ProceduralMeshDocument,
    selection: tuple[str, str] | None,
    project_point: ProjectPoint,
    x: float,
    y: float,
    *,
    hit_radius_px: float = DEFAULT_SKETCH_POINT_HIT_RADIUS_PX,
) -> WallHeightDrag | None:
    handles = selected_wall_height_handles(document, selection)
    best_handle: WallHeightDrag | None = None
    best_distance_sq = hit_radius_px * hit_radius_px
    for handle in handles:
        top_point = wall_height_handle_top_point(handle)
        screen_point = project_point(top_point)
        if screen_point is None:
            continue
        base_screen_point = project_point(handle.base_point)
        if base_screen_point is not None:
            base_dx = screen_point[0] - base_screen_point[0]
            base_dy = screen_point[1] - base_screen_point[1]
            if base_dx * base_dx + base_dy * base_dy < 16.0:
                continue
        dx = screen_point[0] - float(x)
        dy = screen_point[1] - float(y)
        distance_sq = dx * dx + dy * dy
        if distance_sq <= best_distance_sq:
            best_distance_sq = distance_sq
            best_handle = handle
    return best_handle


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


def drag_wall_height_offset_to_ray(
    drag: WallHeightDrag,
    ray_origin: Vec3Data,
    ray_direction: Vec3Data,
) -> float:
    height = _closest_height_on_line(
        drag.base_point,
        drag.normal,
        ray_origin,
        ray_direction,
        drag.effective_height,
    )
    height = max(MIN_WALL_CORNER_HEIGHT, height)
    return height - drag.base_height


def selected_sketch_point_source(
    document: ProceduralMeshDocument,
    selection: tuple[str, str] | None,
):
    sources = selected_sketch_point_sources(document, selection)
    if not sources:
        return None
    return sources[0]


def selected_sketch_point_sources(
    document: ProceduralMeshDocument,
    selection: tuple[str, str] | None,
):
    if selection is None:
        return []
    kind, item_id = selection
    if kind == "contour":
        contour_ref = document.find_contour_ref(item_id)
        if contour_ref is None:
            return []
        sketch, contour = contour_ref
        return [("contour", contour.id, sketch.contour_points(contour))]
    if kind == "path":
        path_ref = document.find_path_ref(item_id)
        if path_ref is None:
            return []
        sketch, path = path_ref
        return [("path", path.id, sketch.path_points(path))]
    if kind == "operation":
        operation = document.find_operation(item_id)
        if operation is None or operation.kind != OPERATION_KIND_WALL:
            return []
        sketch = document.find_sketch(str(operation.params.get("source_sketch_id", "")))
        if sketch is None:
            return []
        input_ids = set(operation.inputs)
        sources = []
        for path in sketch.paths:
            if path.id in input_ids:
                sources.append(("path", path.id, sketch.path_points(path)))
        for contour in sketch.outer_contours():
            if contour.id not in input_ids:
                continue
            if sketch.hole_contours_for_outer(contour.id):
                continue
            sources.append(("contour", contour.id, sketch.contour_points(contour)))
        return sources
    return []


def selected_wall_height_handles(
    document: ProceduralMeshDocument,
    selection: tuple[str, str] | None,
) -> list[WallHeightDrag]:
    if selection is None or selection[0] != "operation":
        return []
    operation = document.find_operation(selection[1])
    if operation is None or operation.kind != OPERATION_KIND_WALL:
        return []
    source_sketch_id = str(operation.params.get("source_sketch_id", ""))
    sketch = document.find_sketch(source_sketch_id)
    if sketch is None:
        return []
    base_height = _param_float(operation.params, "height", 3.0)
    input_ids = set(operation.inputs)
    handles: list[WallHeightDrag] = []
    for path in sketch.paths:
        if path.id not in input_ids:
            continue
        base_points = sketch.path_points(path)
        heights = wall_effective_corner_heights(
            operation.params,
            path.id,
            len(base_points),
            base_height,
            operation_id=operation.id,
        )
        for index, base_point in enumerate(base_points):
            handles.append(
                WallHeightDrag(
                    operation_id=operation.id,
                    source_kind="path",
                    source_id=path.id,
                    point_index=index,
                    base_point=base_point,
                    normal=sketch.plane.normal,
                    base_height=base_height,
                    effective_height=heights[index],
                )
            )
    for contour in sketch.outer_contours():
        if contour.id not in input_ids:
            continue
        if sketch.hole_contours_for_outer(contour.id):
            continue
        base_points = sketch.contour_points(contour)
        heights = wall_effective_corner_heights(
            operation.params,
            contour.id,
            len(base_points),
            base_height,
            operation_id=operation.id,
        )
        for index, base_point in enumerate(base_points):
            handles.append(
                WallHeightDrag(
                    operation_id=operation.id,
                    source_kind="contour",
                    source_id=contour.id,
                    point_index=index,
                    base_point=base_point,
                    normal=sketch.plane.normal,
                    base_height=base_height,
                    effective_height=heights[index],
                )
            )
    return handles


def wall_height_handle_top_point(handle: WallHeightDrag) -> Vec3Data:
    return (
        handle.base_point[0] + handle.normal[0] * handle.effective_height,
        handle.base_point[1] + handle.normal[1] * handle.effective_height,
        handle.base_point[2] + handle.normal[2] * handle.effective_height,
    )


def sketch_point_ref_by_drag(document: ProceduralMeshDocument, drag: SketchPointDrag):
    if drag.kind == "contour":
        return document.find_contour_ref(drag.item_id)
    if drag.kind == "path":
        return document.find_path_ref(drag.item_id)
    return None


def _closest_height_on_line(
    base_point: Vec3Data,
    normal: Vec3Data,
    ray_origin: Vec3Data,
    ray_direction: Vec3Data,
    fallback_height: float,
) -> float:
    ux, uy, uz = ray_direction
    vx, vy, vz = normal
    wx = ray_origin[0] - base_point[0]
    wy = ray_origin[1] - base_point[1]
    wz = ray_origin[2] - base_point[2]
    a = ux * ux + uy * uy + uz * uz
    b = ux * vx + uy * vy + uz * vz
    c = vx * vx + vy * vy + vz * vz
    d = ux * wx + uy * wy + uz * wz
    e = vx * wx + vy * wy + vz * wz
    denom = a * c - b * b
    if abs(denom) < 1.0e-9:
        return float(fallback_height)
    return (a * e - b * d) / denom


def _param_float(params: dict, key: str, default: float) -> float:
    try:
        return float(params.get(key, default))
    except Exception:
        return float(default)


__all__ = [
    "DEFAULT_SKETCH_POINT_HIT_RADIUS_PX",
    "ProjectPoint",
    "SketchPointDrag",
    "WallHeightDrag",
    "drag_point_to_ray",
    "drag_wall_height_offset_to_ray",
    "pick_selected_sketch_point",
    "pick_selected_wall_height_point",
    "selected_sketch_point_source",
    "selected_sketch_point_sources",
    "selected_wall_height_handles",
    "sketch_point_ref_by_drag",
    "wall_height_handle_top_point",
]
