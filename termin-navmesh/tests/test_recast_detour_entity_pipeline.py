"""Artifact-free Recast/Detour pipeline tests for entity geometry."""

from __future__ import annotations

import uuid

import pytest


try:
    from termin.geombase import Pose3, Vec3
    from termin.mesh import MeshComponent, TcMesh
    from termin.navmesh import (
        DetourQuerySession,
        MeshSource,
        RecastNavMeshBuilderComponent,
        navmesh_bake_frame_from_pose,
        navmesh_bake_to_world_point,
        navmesh_world_to_bake_point,
    )
    from termin.scene import Entity
    from tmesh import CubeMesh
except ImportError as exc:  # pragma: no cover - depends on built SDK availability.
    pytestmark = pytest.mark.skip(reason=str(exc))


def _configure_builder(builder: RecastNavMeshBuilderComponent) -> None:
    builder.cell_size = 0.2
    builder.cell_height = 0.1
    builder.agent_height = 1.0
    builder.agent_radius = 0.2
    builder.agent_max_climb = 0.5
    builder.agent_max_slope = 45.0
    builder.min_region_area = 0
    builder.merge_region_area = 0
    builder.build_detail_mesh = True


def _attach_cube_mesh(entity: Entity, name_prefix: str) -> MeshComponent:
    mesh_component = MeshComponent()
    mesh_name = f"{name_prefix}-{uuid.uuid4()}"
    mesh_component.mesh = TcMesh.from_mesh3(CubeMesh(size=1.0), mesh_name)
    entity.add_component(mesh_component)
    return mesh_component


def _build_query_session(builder: RecastNavMeshBuilderComponent) -> DetourQuerySession:
    recast_result = builder.build_from_entity_geometry()
    assert recast_result.success, recast_result.error
    assert recast_result.poly_count() > 0

    tile_result = builder.build_detour_tile_data(recast_result)
    assert tile_result.success, tile_result.error
    assert tile_result.data_size() > 0
    assert isinstance(tile_result.data, bytes)

    query = DetourQuerySession()
    assert query.load_tile_data(tile_result.data, "pytest-in-memory")
    assert query.is_ready()
    return query


def _assert_query_path(query: DetourQuerySession, start: tuple[float, float, float],
                       end: tuple[float, float, float]) -> None:
    start_closest = query.closest_point(start)
    end_closest = query.closest_point(end)
    assert start_closest.success
    assert start_closest.over_poly
    assert end_closest.success
    assert end_closest.over_poly

    path = query.find_path(start, end)
    assert len(path) == 2
    assert path[0][0] == pytest.approx(start[0])
    assert path[0][1] == pytest.approx(start[1])
    assert path[-1][0] == pytest.approx(end[0])
    assert path[-1][1] == pytest.approx(end[1])


def test_scaled_translated_cube_keeps_scale_in_bake_space_pathfinding() -> None:
    root = Entity("navmesh_scaled_root")
    root.transform.set_local_position(Vec3(10.0, 20.0, 0.0))
    root.transform.set_local_scale(5.0, 5.0, 0.3)

    builder = RecastNavMeshBuilderComponent()
    root.add_component(builder)
    _configure_builder(builder)
    _attach_cube_mesh(root, "navmesh-scaled-root-cube")

    query = _build_query_session(builder)

    _assert_query_path(
        query,
        start=(-1.5, -1.5, 0.2),
        end=(1.5, 1.5, 0.2),
    )


def test_world_space_query_uses_builder_pose_frame() -> None:
    root = Entity("navmesh_world_space_root")
    root.transform.set_local_position(Vec3(10.0, 20.0, 0.0))
    root.transform.set_local_rotation(Pose3.rotateZ(1.5707963267948966).ang)
    root.transform.set_local_scale(5.0, 5.0, 0.3)

    builder = RecastNavMeshBuilderComponent()
    root.add_component(builder)
    _configure_builder(builder)
    _attach_cube_mesh(root, "navmesh-world-space-cube")

    query = _build_query_session(builder)
    bake_frame = navmesh_bake_frame_from_pose(root.transform.global_pose())

    bake_start = (-1.5, -1.5, 0.2)
    bake_end = (1.5, 1.5, 0.2)
    world_start = navmesh_bake_to_world_point(bake_frame, bake_start)
    world_end = navmesh_bake_to_world_point(bake_frame, bake_end)

    assert navmesh_world_to_bake_point(bake_frame, world_start) == pytest.approx(bake_start)
    assert navmesh_world_to_bake_point(bake_frame, world_end) == pytest.approx(bake_end)

    bake_closest = query.closest_point(bake_start)
    world_closest = query.closest_point_world(bake_frame, world_start)
    assert world_closest.success
    assert world_closest.over_poly
    assert bake_closest.success
    assert world_closest.point == pytest.approx(
        navmesh_bake_to_world_point(bake_frame, bake_closest.point)
    )

    bake_path = query.find_path(bake_start, bake_end)
    world_path = query.find_path_world(bake_frame, world_start, world_end)
    assert len(world_path) == len(bake_path) == 2
    for world_point, bake_point in zip(world_path, bake_path, strict=True):
        assert world_point == pytest.approx(navmesh_bake_to_world_point(bake_frame, bake_point))


def test_descendant_mesh_source_keeps_child_transform_scale() -> None:
    root = Entity("navmesh_descendant_root")
    root.transform.set_local_position(Vec3(10.0, 20.0, 0.0))

    builder = RecastNavMeshBuilderComponent()
    root.add_component(builder)
    _configure_builder(builder)
    builder.mesh_source = MeshSource.AllDescendants.value

    child = root.create_child("navmesh_descendant_cube")
    child.transform.set_local_position(Vec3(2.0, 0.0, 0.0))
    child.transform.set_local_scale(4.0, 4.0, 0.3)
    _attach_cube_mesh(child, "navmesh-descendant-cube")

    query = _build_query_session(builder)

    _assert_query_path(
        query,
        start=(0.5, -1.0, 0.2),
        end=(3.5, 1.0, 0.2),
    )


def test_current_mesh_source_does_not_implicitly_use_child_geometry() -> None:
    root = Entity("navmesh_current_mesh_root")
    builder = RecastNavMeshBuilderComponent()
    root.add_component(builder)
    _configure_builder(builder)
    builder.mesh_source = MeshSource.CurrentMesh.value

    child = root.create_child("navmesh_current_mesh_child")
    child.transform.set_local_scale(4.0, 4.0, 0.3)
    _attach_cube_mesh(child, "navmesh-current-mesh-child-cube")

    result = builder.build_from_entity_geometry()
    assert not result.success
    assert result.error == "no mesh geometry found"
