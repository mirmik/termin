"""Raycast helpers for procedural CSG documents."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import numpy as np

from tcbase import log

from termin.csg._csg_native import to_mesh3
from termin.csg.document_eval import evaluate_document
from termin.csg.procedural_document import ProceduralMeshDocument, ProceduralPlane

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
    ray_origin: Vec3Data,
    ray_direction: Vec3Data,
) -> CsgRaycastHit | None:
    """Raycast all evaluated solids in document-local coordinates."""

    direction = _normalized(ray_direction)
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
            distance = _ray_triangle_distance(ray_origin, direction, a, b, c)
            if distance is None:
                continue
            if best_hit is not None and distance >= best_hit.distance:
                continue
            point = _v_add(ray_origin, _v_mul(direction, distance))
            normal = _triangle_normal(a, b, c)
            if _dot(normal, direction) > 0.0:
                normal = _v_mul(normal, -1.0)
            best_hit = CsgRaycastHit(
                operation_id=evaluated.operation_id,
                contour_id=evaluated.contour_id,
                triangle_index=index // 3,
                point=point,
                normal=normal,
                distance=distance,
                vertices=(a, b, c),
            )
    return best_hit


def sketch_plane_from_hit(hit: CsgRaycastHit) -> ProceduralPlane:
    """Build a stable sketch plane from a CSG raycast hit."""

    a, b, c = hit.vertices
    normal = _normalized(hit.normal)
    candidates = (_v_sub(b, a), _v_sub(c, b), _v_sub(a, c))
    x_axis = (1.0, 0.0, 0.0)
    for candidate in candidates:
        tangent = _v_sub(candidate, _v_mul(normal, _dot(candidate, normal)))
        if _norm(tangent) > 1.0e-6:
            x_axis = _normalized(tangent)
            break
    y_axis = _normalized(_cross(normal, x_axis))
    return ProceduralPlane(origin=hit.point, x_axis=x_axis, y_axis=y_axis)


def ray_plane_intersection(
    ray_origin: Vec3Data,
    ray_direction: Vec3Data,
    plane: ProceduralPlane,
) -> Vec3Data | None:
    normal = plane.normal
    direction = _normalized(ray_direction)
    denom = _dot(direction, normal)
    if abs(denom) < 1.0e-9:
        return None
    distance = _dot(_v_sub(plane.origin, ray_origin), normal) / denom
    if distance < 0.0:
        return None
    return _v_add(ray_origin, _v_mul(direction, distance))


def _ray_triangle_distance(
    origin: Vec3Data,
    direction: Vec3Data,
    a: Vec3Data,
    b: Vec3Data,
    c: Vec3Data,
) -> float | None:
    eps = 1.0e-8
    edge1 = _v_sub(b, a)
    edge2 = _v_sub(c, a)
    pvec = _cross(direction, edge2)
    det = _dot(edge1, pvec)
    if abs(det) < eps:
        return None
    inv_det = 1.0 / det
    tvec = _v_sub(origin, a)
    u = _dot(tvec, pvec) * inv_det
    if u < 0.0 or u > 1.0:
        return None
    qvec = _cross(tvec, edge1)
    v = _dot(direction, qvec) * inv_det
    if v < 0.0 or u + v > 1.0:
        return None
    distance = _dot(edge2, qvec) * inv_det
    if distance < eps:
        return None
    return distance


def _triangle_normal(a: Vec3Data, b: Vec3Data, c: Vec3Data) -> Vec3Data:
    return _normalized(_cross(_v_sub(b, a), _v_sub(c, a)))


def _v_add(a: Vec3Data, b: Vec3Data) -> Vec3Data:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _v_sub(a: Vec3Data, b: Vec3Data) -> Vec3Data:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _v_mul(a: Vec3Data, k: float) -> Vec3Data:
    return (a[0] * k, a[1] * k, a[2] * k)


def _dot(a: Vec3Data, b: Vec3Data) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3Data, b: Vec3Data) -> Vec3Data:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm(a: Vec3Data) -> float:
    return sqrt(_dot(a, a))


def _normalized(a: Vec3Data) -> Vec3Data:
    n = _norm(a)
    if n < 1.0e-9:
        return (0.0, 0.0, 1.0)
    return (a[0] / n, a[1] / n, a[2] / n)


__all__ = [
    "CsgRaycastHit",
    "ray_plane_intersection",
    "raycast_document",
    "sketch_plane_from_hit",
]
