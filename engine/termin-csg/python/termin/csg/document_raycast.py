"""Raycast helpers for procedural CSG documents."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from tcbase import log

from termin.csg._csg_native import to_mesh3
from termin.csg.document_eval import evaluate_document
from termin.csg.procedural_document import ProceduralMeshDocument, ProceduralPlane
from termin.geombase import Ray3, Vec3

Vec3Data = tuple[float, float, float]
_RAY_TRIANGLE_EPSILON = 1.0e-8


@dataclass
class CsgRaycastHit:
    operation_id: str
    contour_id: str
    triangle_index: int
    point: Vec3Data
    normal: Vec3Data
    distance: float
    vertices: tuple[Vec3Data, Vec3Data, Vec3Data]


def raycast_document(
    document: ProceduralMeshDocument,
    ray: Ray3,
) -> CsgRaycastHit | None:
    """Raycast all evaluated solids in document-local coordinates."""

    checked_ray = _checked_ray(ray, "document raycast")
    if checked_ray is None:
        return None

    best_hit: CsgRaycastHit | None = None
    for evaluated in evaluate_document(document):
        try:
            mesh = to_mesh3(evaluated.solid, "csg-raycast-solid", "", True)
            vertices = np.asarray(mesh.vertices, dtype=np.float32).reshape(-1, 3)
            triangles = np.asarray(mesh.triangles, dtype=np.uint32).reshape(-1)
        except Exception as e:
            log.error(
                "[CsgRaycast] failed to build raycast mesh "
                f"operation='{evaluated.operation_id}' contour='{evaluated.contour_id}': {e}"
            )
            continue

        transformed = [
            Vec3(evaluated.point_transform((float(v[0]), float(v[1]), float(v[2]))))
            for v in vertices
        ]
        if any(not vertex.is_finite() for vertex in transformed):
            log.error(
                "[CsgRaycast] rejected non-finite transformed geometry "
                f"operation='{evaluated.operation_id}' contour='{evaluated.contour_id}'"
            )
            continue
        for index in range(0, len(triangles), 3):
            a = transformed[int(triangles[index])]
            b = transformed[int(triangles[index + 1])]
            c = transformed[int(triangles[index + 2])]
            triangle_hit = checked_ray.try_intersect_triangle(
                a,
                b,
                c,
                epsilon=_RAY_TRIANGLE_EPSILON,
            )
            if triangle_hit is None or triangle_hit.ray_parameter < _RAY_TRIANGLE_EPSILON:
                continue
            distance = triangle_hit.ray_parameter
            if best_hit is not None and distance >= best_hit.distance:
                continue
            point = _vec3_data(checked_ray.point_at(distance))
            normal = triangle_hit.normal
            if normal.dot(checked_ray.direction) > 0.0:
                normal = -normal
            best_hit = CsgRaycastHit(
                operation_id=evaluated.operation_id,
                contour_id=evaluated.contour_id,
                triangle_index=index // 3,
                point=point,
                normal=_vec3_data(normal),
                distance=distance,
                vertices=(_vec3_data(a), _vec3_data(b), _vec3_data(c)),
            )
    return best_hit


def sketch_plane_from_hit(hit: CsgRaycastHit) -> ProceduralPlane | None:
    """Build a stable sketch plane from a CSG raycast hit."""

    a, b, c = hit.vertices
    normal = Vec3(hit.normal).try_normalized()
    if normal is None:
        log.error("[CsgRaycast] cannot build sketch plane: hit normal is non-finite or degenerate")
        return None

    candidates = (Vec3(b) - Vec3(a), Vec3(c) - Vec3(b), Vec3(a) - Vec3(c))
    for candidate in candidates:
        x_axis = (candidate - normal * candidate.dot(normal)).try_normalized(1.0e-6)
        if x_axis is None:
            continue
        y_axis = normal.cross(x_axis).try_normalized(1.0e-6)
        if y_axis is not None:
            return ProceduralPlane(
                origin=hit.point,
                x_axis=_vec3_data(x_axis),
                y_axis=_vec3_data(y_axis),
            )

    log.error("[CsgRaycast] cannot build sketch plane: hit triangle has no reliable tangent")
    return None


def ray_plane_intersection(
    ray: Ray3,
    plane: ProceduralPlane,
) -> Vec3Data | None:
    plane_origin = Vec3(plane.origin)
    plane_normal = Vec3(plane.normal)
    point = ray.try_intersect_plane(
        plane_origin,
        plane_normal,
        forward_only=True,
        epsilon=1.0e-9,
    )
    if point is None:
        return None
    return _vec3_data(point)


def _checked_ray(ray: Ray3, operation: str) -> Ray3 | None:
    direction = ray.direction.try_normalized()
    if not ray.origin.is_finite() or direction is None:
        log.error(f"[CsgRaycast] {operation} rejected a non-finite or degenerate ray")
        return None
    return Ray3(ray.origin, direction)


def _vec3_data(value: Vec3) -> Vec3Data:
    return (float(value.x), float(value.y), float(value.z))


__all__ = [
    "CsgRaycastHit",
    "ray_plane_intersection",
    "raycast_document",
    "sketch_plane_from_hit",
]
