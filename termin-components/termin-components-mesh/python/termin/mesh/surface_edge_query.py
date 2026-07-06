"""Entity-level helpers for TcMesh surface edge queries."""

from __future__ import annotations

from dataclasses import dataclass

from tcbase import log
from tcbase._geom_native import Vec3


@dataclass(frozen=True)
class SurfaceEdgeHit:
    point: Vec3
    indices: tuple[int, int]
    distance: float
    side: int


def find_surface_edge_for_entity(
    entity,
    mesh_point: Vec3,
    mesh_normal: Vec3,
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
    mesh_point: Vec3,
    mesh_normal: Vec3,
    triangle_index: int,
    edge_direction: Vec3,
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
    mesh_point: Vec3,
    mesh_normal: Vec3,
    triangle_index: int,
    edge_direction: Vec3 | None,
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
    local_up = _world_vector_to_mesh_local(pose, inverse_mesh_offset, Vec3(0.0, 0.0, 1.0))

    if edge_direction is None:
        edge = mesh.find_surface_edge(
            int(triangle_index),
            local_point,
            local_normal,
            local_up,
            metric,
        )
    else:
        local_edge_direction = _world_vector_to_mesh_local(pose, inverse_mesh_offset, edge_direction)
        edge = mesh.find_surface_edge_aligned(
            int(triangle_index),
            local_point,
            local_normal,
            local_edge_direction,
            float(max_angle_degrees),
            local_up,
            metric,
        )

    if edge is None:
        return None

    local_edge = edge["point"]
    world_edge = _mesh_point_to_world(pose, mesh_offset, local_edge)
    indices = edge["indices"]
    return SurfaceEdgeHit(
        world_edge,
        (int(indices[0]), int(indices[1])),
        float(edge["distance"]),
        int(edge["side"]),
    )


def _world_point_to_mesh_local(pose, inverse_mesh_offset, point: Vec3) -> Vec3:
    return inverse_mesh_offset.transform_point(pose.point_to_local(point))


def _world_vector_to_mesh_local(pose, inverse_mesh_offset, vector: Vec3) -> Vec3:
    return inverse_mesh_offset.transform_direction(pose.vector_to_local(vector))


def _mesh_point_to_world(pose, mesh_offset, point: Vec3) -> Vec3:
    return pose.transform_point(mesh_offset.transform_point(point))
