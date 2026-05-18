"""Entity-level helpers for TcMesh surface edge queries."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from tcbase import log
from tcbase._geom_native import Vec3


@dataclass(frozen=True)
class SurfaceEdgeHit:
    point: tuple[float, float, float]
    indices: tuple[int, int]
    distance: float
    side: int


def find_surface_edge_for_entity(
    entity,
    mesh_point: tuple[float, float, float],
    mesh_normal: tuple[float, float, float],
    triangle_index: int,
) -> SurfaceEdgeHit | None:
    return _find_surface_edge_for_entity(
        entity,
        mesh_point,
        mesh_normal,
        triangle_index,
        None,
        0.0,
    )


def find_aligned_surface_edge_for_entity(
    entity,
    mesh_point: tuple[float, float, float],
    mesh_normal: tuple[float, float, float],
    triangle_index: int,
    edge_direction: tuple[float, float, float],
    max_angle_degrees: float,
) -> SurfaceEdgeHit | None:
    return _find_surface_edge_for_entity(
        entity,
        mesh_point,
        mesh_normal,
        triangle_index,
        edge_direction,
        max_angle_degrees,
    )


def _find_surface_edge_for_entity(
    entity,
    mesh_point: tuple[float, float, float],
    mesh_normal: tuple[float, float, float],
    triangle_index: int,
    edge_direction: tuple[float, float, float] | None,
    max_angle_degrees: float,
) -> SurfaceEdgeHit | None:
    from termin.mesh.mesh_component import MeshComponent

    mesh_component = entity.get_component(MeshComponent)
    if mesh_component is None:
        log.error("[SurfaceEdgeQuery] picked entity has no MeshComponent")
        return None

    mesh = mesh_component.mesh
    if mesh is None:
        log.error("[SurfaceEdgeQuery] MeshComponent has no mesh")
        return None

    pose = entity.transform.global_pose()
    mesh_offset = mesh_component.get_mesh_offset_matrix()
    inverse_mesh_offset = mesh_offset.inverse()
    metric = entity.transform.global_scale
    local_point = _world_point_to_mesh_local(pose, inverse_mesh_offset, mesh_point)
    local_normal = _world_vector_to_mesh_local(pose, inverse_mesh_offset, mesh_normal)
    local_up = _world_vector_to_mesh_local(pose, inverse_mesh_offset, (0.0, 0.0, 1.0))

    if edge_direction is None:
        edge = mesh.find_surface_edge(
            int(triangle_index),
            _tuple3(local_point),
            _tuple3(local_normal),
            _tuple3(local_up),
            _tuple3(metric),
        )
    else:
        local_edge_direction = _world_vector_to_mesh_local(pose, inverse_mesh_offset, edge_direction)
        edge = mesh.find_surface_edge_aligned(
            int(triangle_index),
            _tuple3(local_point),
            _tuple3(local_normal),
            _tuple3(local_edge_direction),
            float(max_angle_degrees),
            _tuple3(local_up),
            _tuple3(metric),
        )

    if edge is None:
        return None

    local_edge = np.asarray(edge["point"], dtype=float)
    world_edge = _mesh_point_to_world(pose, mesh_offset, local_edge)
    indices = edge["indices"]
    return SurfaceEdgeHit(
        _tuple3(world_edge),
        (int(indices[0]), int(indices[1])),
        float(edge["distance"]),
        int(edge["side"]),
    )


def _tuple3(v) -> tuple[float, float, float]:
    return (float(v[0]), float(v[1]), float(v[2]))


def _vec3(point: tuple[float, float, float]) -> Vec3:
    return Vec3(point[0], point[1], point[2])


def _world_point_to_mesh_local(pose, inverse_mesh_offset, point: tuple[float, float, float]) -> Vec3:
    return inverse_mesh_offset.transform_point(pose.point_to_local(_vec3(point)))


def _world_vector_to_mesh_local(pose, inverse_mesh_offset, vector: tuple[float, float, float]) -> Vec3:
    return inverse_mesh_offset.transform_direction(pose.vector_to_local(_vec3(vector)))


def _mesh_point_to_world(pose, mesh_offset, point) -> Vec3:
    return pose.transform_point(mesh_offset.transform_point(_vec3(_tuple3(point))))
