from __future__ import annotations

import numpy as np
import pytest

import termin.bootstrap
from termin.geombase import Affine3d, Basis3d, Ray3, Rect2, Vec2, Vec3
from termin.navmesh import DetourPathfindingWorldComponent, PathfindingWorld
from termin.navmesh.pathfinding import NavMeshGraph, RegionGraph
import termin.navmesh.pathfinding_world_component as pathfinding_world_module
from termin.navmesh.pathfinding_world_component import PathfindingWorldComponent
from termin.scene import TcScene


class _StaticTransform:
    def __init__(self, affine: Affine3d) -> None:
        self._affine = affine

    def global_affine(self) -> Affine3d:
        return self._affine


class _StaticEntity:
    def __init__(self, affine: Affine3d) -> None:
        self.transform = _StaticTransform(affine)


class _DirectOnlyAffine:
    def __init__(self, affine: Affine3d) -> None:
        self._affine = affine

    def is_finite(self):
        return self._affine.is_finite()

    def try_inverse_transform_point(self, point):
        return self._affine.try_inverse_transform_point(point)

    def try_inverse_transform_vector(self, vector):
        return self._affine.try_inverse_transform_vector(vector)

    def transform_point(self, point):
        return self._affine.transform_point(point)

    def try_inverse(self):
        pytest.fail("navmesh queries must not materialize an inverse affine")


class _RecordingLog:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)


def _single_triangle_world(affine: Affine3d) -> PathfindingWorldComponent:
    vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
        dtype=np.float64,
    )
    triangles = np.array([[0, 1, 2]], dtype=np.int32)

    world = PathfindingWorldComponent()
    world._navmesh_graph = NavMeshGraph()
    world._navmesh_graph.add_region(RegionGraph.from_mesh(vertices, triangles, region_id=0))
    world._region_entities[0] = _StaticEntity(affine)
    return world


@pytest.fixture(scope="module", autouse=True)
def _bootstrap_runtime_extensions():
    termin.bootstrap.bootstrap_player()
    try:
        yield
    finally:
        termin.bootstrap.shutdown_player()


def test_pathfinding_world_tracks_multiple_components_on_one_entity() -> None:
    scene = TcScene.create("pathfinding-world-multiple-components")
    try:
        entity = scene.create_entity("navmesh-owner")
        world = PathfindingWorld.ensure_scene(scene)
        assert world is not None
        assert world.size == 0
        assert world.candidates_for_world_point((0.0, 0.0, 0.0)) == []

        entity.add_component(DetourPathfindingWorldComponent())
        entity.add_component(DetourPathfindingWorldComponent())

        assert world.size == 2
        world.rebuild_from_scene()
        assert world.size == 2
    finally:
        scene.destroy()


def test_screen_raycast_rejects_camera_projection_failure() -> None:
    class FailingCamera:
        def try_screen_point_to_ray(self, screen_point, viewport):
            assert type(screen_point) is Vec2
            assert (screen_point.x, screen_point.y) == (10.0, 20.0)
            assert type(viewport) is Rect2
            assert (viewport.x, viewport.y, viewport.width, viewport.height) == (0.0, 0.0, 640.0, 480.0)
            return None

        def screen_point_to_ray(self, screen_point, viewport):
            pytest.fail("optional raycast must use the checked camera API")

    def unexpected_raycast(*args, **kwargs):
        pytest.fail("raycast must not run without a checked ray")

    world = PathfindingWorldComponent()
    world.raycast = unexpected_raycast

    assert (
        world.raycast_from_screen(
            Vec2(10.0, 20.0),
            FailingCamera(),
            Rect2(0.0, 0.0, 640.0, 480.0),
        )
        is None
    )


def test_screen_raycast_does_not_hide_camera_api_regressions() -> None:
    class BrokenCamera:
        def try_screen_point_to_ray(self, screen_point, viewport):
            raise AttributeError("binding contract changed")

    world = PathfindingWorldComponent()

    with pytest.raises(AttributeError, match="binding contract changed"):
        world.raycast_from_screen(
            Vec2(10.0, 20.0),
            BrokenCamera(),
            Rect2(0.0, 0.0, 640.0, 480.0),
        )


def test_screen_raycast_forwards_canonical_ray_without_flattening() -> None:
    ray = Ray3(Vec3(1.0e12, -2.0e12, 3.0e12), Vec3(0.0, 0.0, -2.0))
    expected = (np.array([1.0, 2.0, 3.0]), 7.0, 4, 5)

    class Camera:
        def try_screen_point_to_ray(self, screen_point, viewport):
            assert type(screen_point) is Vec2
            assert type(viewport) is Rect2
            return ray

    def recording_raycast(candidate, max_distance=1000.0):
        assert candidate is ray
        assert type(candidate) is Ray3
        assert max_distance == 42.0
        return expected

    world = PathfindingWorldComponent()
    world.raycast = recording_raycast

    result = world.raycast_from_screen(
        Vec2(10.0, 20.0),
        Camera(),
        Rect2(0.0, 0.0, 640.0, 480.0),
        max_distance=42.0,
    )

    assert result is expected


def test_agent_click_forwards_canonical_ray_without_flattening() -> None:
    from tcbase import Action, MouseButton
    from termin.navmesh.agent_component import NavMeshAgentComponent

    ray = Ray3(Vec3(10.0, 20.0, 30.0), Vec3(0.0, -1.0, 0.0))

    class Viewport:
        def screen_point_to_ray(self, x, y):
            assert (x, y) == (12.0, 34.0)
            return ray

    class Event:
        button = MouseButton.LEFT
        action = Action.PRESS
        x = 12.0
        y = 34.0
        viewport = Viewport()

    class RecordingWorld:
        def __init__(self) -> None:
            self.received = None

        def raycast(self, candidate):
            self.received = candidate
            return None

    world = RecordingWorld()
    agent = NavMeshAgentComponent()
    agent._pathfinding_world = world

    agent.on_mouse_button(Event())

    assert world.received is ray
    assert type(world.received) is Ray3


def test_raycast_rejects_legacy_flat_origin_direction_form() -> None:
    world = PathfindingWorldComponent()
    origin = np.array([0.25, 0.25, 1.0], dtype=np.float64)
    direction = np.array([0.0, 0.0, -1.0], dtype=np.float64)

    with pytest.raises(TypeError, match="expects a Ray3"):
        world.raycast(origin, direction)


@pytest.mark.parametrize(
    ("affine", "expected_reason"),
    [
        (Affine3d.scaling(0.0, 1.0, 1.0), "singular"),
        (
            Affine3d(Basis3d.identity(), Vec3(float("nan"), 0.0, 0.0)),
            "non-finite",
        ),
    ],
)
def test_invalid_region_affine_cannot_contribute_a_false_hit(
    affine: Affine3d,
    expected_reason: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recording_log = _RecordingLog()
    monkeypatch.setattr(pathfinding_world_module, "log", recording_log)
    world = _single_triangle_world(affine)

    ray = Ray3(Vec3(0.25, 0.25, 1.0), Vec3(0.0, 0.0, -1.0))
    point_on_identity_triangle = np.array([0.25, 0.25, 0.0], dtype=np.float64)

    assert world.raycast(ray, max_distance=10.0) is None
    assert world.find_containing_triangle(point_on_identity_triangle) is None
    assert any(expected_reason in message for message in recording_log.errors)


def test_non_finite_world_query_is_not_reported_as_a_singular_affine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recording_log = _RecordingLog()
    monkeypatch.setattr(pathfinding_world_module, "log", recording_log)
    world = _single_triangle_world(Affine3d.identity())

    assert world.find_containing_triangle(np.array([float("nan"), 0.0, 0.0])) is None
    assert any("non-finite world point" in message for message in recording_log.errors)
    assert all("singular" not in message for message in recording_log.errors)


def test_raycast_roundtrips_oriented_nonuniform_affine() -> None:
    # Columns encode a 90-degree Y rotation followed by a non-uniform scale.
    affine = Affine3d(
        Basis3d(
            Vec3(0.0, 0.0, -2.0),
            Vec3(0.0, 3.0, 0.0),
            Vec3(0.5, 0.0, 0.0),
        ),
        Vec3(10.0, 20.0, 30.0),
    )
    world = _single_triangle_world(affine)

    local_hit = Vec3(0.25, 0.25, 0.0)
    world_hit = affine.transform_point(local_hit)
    world_origin = affine.transform_point(Vec3(0.25, 0.25, 2.0))
    world_direction = affine.transform_vector(Vec3(0.0, 0.0, -1.0)).try_normalized()
    assert world_direction is not None

    result = world.raycast(Ray3(world_origin, world_direction), max_distance=10.0)

    assert result is not None
    hit_point, distance, region_id, triangle_id = result
    np.testing.assert_allclose(hit_point, np.asarray(world_hit), atol=1.0e-10)
    assert distance == pytest.approx(1.0)
    assert (region_id, triangle_id) == (0, 0)
    assert world.find_containing_triangle(np.asarray(world_hit)) == (0, 0)


def test_raycast_uses_direct_checked_inverse_transforms_in_large_world() -> None:
    inner = Affine3d(
        Basis3d(
            Vec3(0.0, 0.0, -2.0),
            Vec3(0.0, 3.0, 0.0),
            Vec3(0.5, 0.0, 0.0),
        ),
        Vec3(1.0e12, -2.0e12, 3.0e12),
    )

    transform = _DirectOnlyAffine(inner)
    world = _single_triangle_world(transform)
    expected_hit = inner.transform_point(Vec3(0.25, 0.25, 0.0))
    world_origin = inner.transform_point(Vec3(0.25, 0.25, 2.0))
    world_direction = inner.transform_vector(Vec3(0.0, 0.0, -1.0)).try_normalized()
    assert world_direction is not None

    result = world.raycast(Ray3(world_origin, world_direction), max_distance=10.0)

    assert result is not None
    hit_point, distance, region_id, triangle_id = result
    np.testing.assert_allclose(
        hit_point,
        np.asarray(expected_hit),
        rtol=0.0,
        atol=5.0e-4,
    )
    assert distance == pytest.approx(1.0, abs=5.0e-4)
    assert (region_id, triangle_id) == (0, 0)


def test_point_and_path_queries_use_direct_checked_inverse_in_large_world() -> None:
    inner = Affine3d(
        Basis3d(
            Vec3(0.0, 0.0, -2.0),
            Vec3(0.0, 3.0, 0.0),
            Vec3(0.5, 0.0, 0.0),
        ),
        Vec3(1.0e12, -2.0e12, 3.0e12),
    )
    world = _single_triangle_world(_DirectOnlyAffine(inner))
    world._initialized = True

    local_start = Vec3(0.2, 0.2, 0.0)
    local_end = Vec3(0.3, 0.25, 0.0)
    world_start = np.asarray(inner.transform_point(local_start), dtype=np.float64)
    world_end = np.asarray(inner.transform_point(local_end), dtype=np.float64)

    assert world.find_containing_triangle(world_start) == (0, 0)
    assert world._find_triangle_in_region(world_start, 0) == 0
    assert world._find_nearest_triangle_in_region(world_start, 0) == 0
    assert world.find_path_triangles(world_start, world_end) == [(0, 0)]

    path = world.find_path(world_start, world_end)
    assert path is not None
    assert len(path) == 2
    np.testing.assert_allclose(path[0], world_start, rtol=0.0, atol=5.0e-4)
    np.testing.assert_allclose(path[1], world_end, rtol=0.0, atol=5.0e-4)

    center = world.get_triangle_center(0, 0)
    assert center is not None
    expected_center = np.asarray(inner.transform_point(Vec3(1.0 / 3.0, 1.0 / 3.0, 0.0)))
    np.testing.assert_allclose(center, expected_center, rtol=0.0, atol=5.0e-4)


def test_triangle_center_only_requires_a_valid_forward_affine() -> None:
    affine = Affine3d(
        Basis3d(
            Vec3(0.0, 0.0, 0.0),
            Vec3(0.0, 2.0, 0.0),
            Vec3(0.0, 0.0, 3.0),
        ),
        Vec3(10.0, 20.0, 30.0),
    )
    world = _single_triangle_world(_DirectOnlyAffine(affine))

    center = world.get_triangle_center(0, 0)

    assert center is not None
    expected = np.asarray(affine.transform_point(Vec3(1.0 / 3.0, 1.0 / 3.0, 0.0)))
    np.testing.assert_allclose(center, expected, rtol=0.0, atol=1.0e-12)
