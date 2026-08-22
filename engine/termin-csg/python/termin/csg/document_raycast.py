"""Raycast helpers for procedural CSG documents."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import numpy as np

from tcbase import log

from termin.csg._csg_native import to_mesh3
from termin.csg.document_eval import evaluate_document
from termin.csg.procedural_document import ProceduralMeshDocument, ProceduralPlane
from termin.geombase import Ray3, Vec3

Vec3Data = tuple[float, float, float]


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
            evaluated.point_transform((float(v[0]), float(v[1]), float(v[2])))
            for v in vertices
        ]
        for index in range(0, len(triangles), 3):
            a = transformed[int(triangles[index])]
            b = transformed[int(triangles[index + 1])]
            c = transformed[int(triangles[index + 2])]
            distance = _ray_triangle_distance(checked_ray, a, b, c)
            if distance is None:
                continue
            if best_hit is not None and distance >= best_hit.distance:
                continue
            point = _vec3_data(checked_ray.point_at(distance))
            normal = _triangle_normal(a, b, c)
            if normal is None:
                continue
            if normal.dot(checked_ray.direction) > 0.0:
                normal = -normal
            best_hit = CsgRaycastHit(
                operation_id=evaluated.operation_id,
                contour_id=evaluated.contour_id,
                triangle_index=index // 3,
                point=point,
                normal=_vec3_data(normal),
                distance=distance,
                vertices=(a, b, c),
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


def _ray_triangle_distance(
    ray: Ray3,
    a: Vec3Data,
    b: Vec3Data,
    c: Vec3Data,
) -> float | None:
    eps = 1.0e-8
    vertex_a = Vec3(a)
    vertex_b = Vec3(b)
    vertex_c = Vec3(c)
    if not vertex_a.is_finite() or not vertex_b.is_finite() or not vertex_c.is_finite():
        return None

    edge1 = vertex_b - vertex_a
    edge2 = vertex_c - vertex_a
    pvec = ray.direction.cross(edge2)
    det = edge1.dot(pvec)
    if not isfinite(det) or abs(det) < eps:
        return None
    inv_det = 1.0 / det
    tvec = ray.origin - vertex_a
    u = tvec.dot(pvec) * inv_det
    if not isfinite(u) or u < 0.0 or u > 1.0:
        return None
    qvec = tvec.cross(edge1)
    v = ray.direction.dot(qvec) * inv_det
    if not isfinite(v) or v < 0.0 or u + v > 1.0:
        return None
    distance = edge2.dot(qvec) * inv_det
    if not isfinite(distance) or distance < eps:
        return None
    return distance


def _triangle_normal(a: Vec3Data, b: Vec3Data, c: Vec3Data) -> Vec3 | None:
    return (Vec3(b) - Vec3(a)).cross(Vec3(c) - Vec3(a)).try_normalized()


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
