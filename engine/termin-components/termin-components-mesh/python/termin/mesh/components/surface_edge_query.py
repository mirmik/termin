"""Entity-level helpers for TcMesh surface edge queries."""

from __future__ import annotations

from dataclasses import dataclass

from termin.base import log
from termin.base._geom_native import Mat44f, Vec3


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
    from termin.mesh.components.mesh_component import MeshComponent

    mesh_component = entity.get_component(MeshComponent)
    if mesh_component is None:
        log.error("[SurfaceEdgeQuery] picked entity has no MeshComponent")
        return None

    mesh = mesh_component.mesh
    if mesh is None:
        log.error("[SurfaceEdgeQuery] MeshComponent has no mesh")
        return None

    transform = entity.transform
    mesh_offset = mesh_component.get_mesh_offset_matrix()
    inverse_mesh_offset = mesh_offset.inverse()
    metric = _surface_edge_axis_length_metric(transform, mesh_offset)
    local_point = _world_point_to_mesh_local(
        transform, inverse_mesh_offset, mesh_point
    )
    local_normal = _world_normal_to_mesh_query(transform, mesh_offset, mesh_normal)
    local_up = _world_vector_to_mesh_local(
        transform, inverse_mesh_offset, Vec3(0.0, 0.0, 1.0)
    )

    if edge_direction is None:
        edge = mesh.find_surface_edge(
            int(triangle_index),
            local_point,
            local_normal,
            local_up,
            metric,
        )
    else:
        local_edge_direction = _world_vector_to_mesh_local(
            transform, inverse_mesh_offset, edge_direction
        )
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

    world_edge = _mesh_point_to_world(transform, mesh_offset, edge.point)
    return SurfaceEdgeHit(
        world_edge,
        edge.indices,
        edge.distance,
        edge.side,
    )


def _world_point_to_mesh_local(transform, inverse_mesh_offset, point: Vec3) -> Vec3:
    return _mat44f_transform_point(
        inverse_mesh_offset,
        transform.transform_point_inverse(point),
    )


def _world_vector_to_mesh_local(transform, inverse_mesh_offset, vector: Vec3) -> Vec3:
    return _mat44f_transform_direction(
        inverse_mesh_offset,
        transform.transform_vector_inverse(vector),
    )


def _world_normal_to_mesh_query(
    transform,
    mesh_offset,
    normal: Vec3,
) -> Vec3:
    # A normal is a covector. For local-to-world basis L its local components
    # are L^T * n_world, not L^-1 * n_world. The mesh query owns the subsequent
    # inverse-transpose conversion into its diagonal metric space.
    axis_x, axis_y, axis_z = _mesh_world_basis_axes(transform, mesh_offset)
    return Vec3(
        axis_x.dot(normal),
        axis_y.dot(normal),
        axis_z.dot(normal),
    ).normalized()


def _surface_edge_axis_length_metric(transform, mesh_offset) -> Vec3:
    """Column-length approximation used by the diagonal mesh-query metric."""
    axis_x, axis_y, axis_z = _mesh_world_basis_axes(transform, mesh_offset)
    return Vec3(axis_x.norm(), axis_y.norm(), axis_z.norm())


def _mesh_world_basis_axes(transform, mesh_offset) -> tuple[Vec3, Vec3, Vec3]:
    return (
        transform.transform_vector(
            _mat44f_transform_direction(mesh_offset, Vec3.unit_x())
        ),
        transform.transform_vector(
            _mat44f_transform_direction(mesh_offset, Vec3.unit_y())
        ),
        transform.transform_vector(
            _mat44f_transform_direction(mesh_offset, Vec3.unit_z())
        ),
    )


def _mesh_point_to_world(transform, mesh_offset, point: Vec3) -> Vec3:
    return transform.transform_point(_mat44f_transform_point(mesh_offset, point))


def _mat44f_transform_point(matrix: Mat44f, point: Vec3) -> Vec3:
    """Cross the float matrix boundary without leaking Vec3f into scene math."""
    return matrix.transform_point(point.to_float()).to_double()


def _mat44f_transform_direction(matrix: Mat44f, vector: Vec3) -> Vec3:
    """Cross the float matrix boundary without leaking Vec3f into scene math."""
    return matrix.transform_direction(vector.to_float()).to_double()
