import numpy as np
import pytest

from termin.scene import Entity
from termin.render_components.camera import PerspectiveCameraComponent
from termin.geombase import GeneralPose3, Pose3, ProjectedScreenPoint, Ray3, Rect2, Vec2, Vec3


VIEWPORT_WIDTH = 800
VIEWPORT_HEIGHT = 600
VIEWPORT = Rect2(0.0, 0.0, VIEWPORT_WIDTH, VIEWPORT_HEIGHT)


def build_basic_camera(position=(0.0, 0.0, 0.0)):
    cam_entity = Entity(pose=GeneralPose3(lin=Vec3(*position)), name="camera")
    cam = PerspectiveCameraComponent()
    cam_entity.add_component(cam)
    return cam_entity, cam


def assert_valid_ray(ray, expected_direction):
    origin = np.array(ray.origin, dtype=float)
    direction = np.array(ray.direction, dtype=float)

    assert np.isfinite(origin).all()
    assert np.isfinite(direction).all()
    assert np.linalg.norm(direction) == pytest.approx(1.0, rel=1e-6)
    np.testing.assert_allclose(
        direction,
        np.array(expected_direction, dtype=float),
        rtol=1e-6,
        atol=1e-6,
    )


def test_entity_pose_constructor_rejects_legacy_pose3():
    with pytest.raises(TypeError, match="GeneralPose3"):
        Entity(pose=Pose3.identity(), name="legacy_pose")


def test_center_ray_direction_forward():
    cam_entity, cam = build_basic_camera()
    ray = cam.screen_point_to_ray(Vec2(VIEWPORT_WIDTH * 0.5, VIEWPORT_HEIGHT * 0.5), VIEWPORT)

    # Project uses Y-forward convention (local +Y = forward)
    assert_valid_ray(ray, (0.0, 1.0, 0.0))


def test_try_center_ray_returns_ray():
    cam_entity, cam = build_basic_camera()
    ray = cam.try_screen_point_to_ray(Vec2(VIEWPORT_WIDTH * 0.5, VIEWPORT_HEIGHT * 0.5), VIEWPORT)

    assert ray is not None
    assert type(ray) is Ray3
    assert_valid_ray(ray, (0.0, 1.0, 0.0))


def test_unattached_camera_rejects_missing_view_transform():
    cam = PerspectiveCameraComponent()
    screen_point = Vec2(400.0, 300.0)

    assert cam.try_screen_point_to_ray(screen_point, VIEWPORT) is None
    with pytest.raises(ValueError, match="view transform is unavailable"):
        cam.screen_point_to_ray(screen_point, VIEWPORT)


@pytest.mark.parametrize(
    ("x", "y", "expected_direction"),
    [
        (0.0, VIEWPORT_HEIGHT * 0.5, (-0.5, 0.8660254037844387, 0.0)),
        (VIEWPORT_WIDTH, VIEWPORT_HEIGHT * 0.5, (0.5, 0.8660254037844387, 0.0)),
        (VIEWPORT_WIDTH * 0.5, 0.0, (0.0, 0.917662935482247, 0.3973597071195132)),
        (VIEWPORT_WIDTH * 0.5, VIEWPORT_HEIGHT, (0.0, 0.917662935482247, -0.3973597071195132)),
        (0.0, 0.0, (-0.4681645887845222, 0.8108848540793832, 0.3511234415883917)),
        (VIEWPORT_WIDTH, VIEWPORT_HEIGHT, (0.4681645887845222, 0.8108848540793832, -0.3511234415883917)),
    ],
)
def test_viewport_edge_rays_match_camera_projection(x, y, expected_direction):
    cam_entity, cam = build_basic_camera()
    ray = cam.screen_point_to_ray(Vec2(x, y), VIEWPORT)

    assert_valid_ray(ray, expected_direction)


@pytest.mark.parametrize(
    "viewport",
    [
        Rect2(0.0, 0.0, 0.0, VIEWPORT_HEIGHT),
        Rect2(0.0, 0.0, VIEWPORT_WIDTH, 0.0),
        Rect2(0.0, 0.0, -1.0, VIEWPORT_HEIGHT),
        Rect2(0.0, 0.0, VIEWPORT_WIDTH, float("nan")),
    ],
)
def test_invalid_viewport_is_rejected_without_fallback_ray(viewport):
    cam_entity, cam = build_basic_camera()
    screen_point = Vec2.zero()

    assert cam.try_screen_point_to_ray(screen_point, viewport) is None
    with pytest.raises(ValueError, match="screen_point_to_ray failed"):
        cam.screen_point_to_ray(screen_point, viewport)


def test_flat_screen_projection_inputs_are_rejected_by_binding():
    cam_entity, cam = build_basic_camera()

    with pytest.raises(TypeError):
        cam.try_screen_point_to_ray((400.0, 300.0), VIEWPORT)
    with pytest.raises(TypeError):
        cam.try_screen_point_to_ray(Vec2(400.0, 300.0), (0.0, 0.0, VIEWPORT_WIDTH, VIEWPORT_HEIGHT))
    with pytest.raises(TypeError):
        cam.screen_point_to_ray(400.0, 300.0, VIEWPORT)
    with pytest.raises(TypeError):
        cam.try_project_world_point((0.0, 5.0, 0.0), VIEWPORT)


@pytest.mark.parametrize(
    ("x", "y"),
    [
        (float("nan"), 0.0),
        (float("inf"), 0.0),
        (0.0, float("-inf")),
    ],
)
def test_nonfinite_screen_point_is_rejected(x, y):
    cam_entity, cam = build_basic_camera()
    screen_point = Vec2(x, y)

    assert cam.try_screen_point_to_ray(screen_point, VIEWPORT) is None
    with pytest.raises(ValueError, match="screen_point_to_ray failed"):
        cam.screen_point_to_ray(screen_point, VIEWPORT)


def test_nonfinite_projection_is_rejected():
    cam_entity, cam = build_basic_camera()
    cam.fov_x = float("nan")
    screen_point = Vec2(400.0, 300.0)

    assert cam.try_screen_point_to_ray(screen_point, VIEWPORT) is None
    with pytest.raises(ValueError, match="screen_point_to_ray failed"):
        cam.screen_point_to_ray(screen_point, VIEWPORT)


def test_singular_projection_is_rejected():
    cam_entity, cam = build_basic_camera()
    cam.near_clip = 0.0
    screen_point = Vec2(400.0, 300.0)

    assert cam.try_screen_point_to_ray(screen_point, VIEWPORT) is None
    with pytest.raises(ValueError, match="screen_point_to_ray failed"):
        cam.screen_point_to_ray(screen_point, VIEWPORT)


def test_large_world_camera_preserves_origin_and_direction():
    position = (1.0e12, -2.0e12, 3.0e12)
    cam_entity, cam = build_basic_camera(position)

    ray = cam.try_screen_point_to_ray(Vec2(400.0, 300.0), VIEWPORT)

    assert ray is not None
    assert_valid_ray(ray, (0.0, 1.0, 0.0))
    np.testing.assert_allclose(
        np.array(ray.origin, dtype=float),
        np.array((position[0], position[1] + cam.near_clip, position[2]), dtype=float),
        rtol=0.0,
        atol=2.0e-3,
    )


def test_world_projection_returns_canonical_semantic_value_without_mutating_aspect():
    cam_entity, cam = build_basic_camera()
    cam.aspect = 0.25

    projected = cam.try_project_world_point(Vec3(0.0, 5.0, 0.0), VIEWPORT)

    assert projected is not None
    assert type(projected) is ProjectedScreenPoint
    assert type(projected.screen) is Vec2
    assert projected.screen.x == pytest.approx(VIEWPORT_WIDTH * 0.5)
    assert projected.screen.y == pytest.approx(VIEWPORT_HEIGHT * 0.5)
    assert 0.0 < projected.depth < 1.0
    assert projected.view_point.y == pytest.approx(5.0)
    assert cam.aspect == pytest.approx(0.25)


def test_world_projection_preserves_large_world_local_coordinates():
    position = (1.0e12, -2.0e12, 3.0e12)
    cam_entity, cam = build_basic_camera(position)
    world_point = Vec3(position[0], position[1] + 5.0, position[2])

    projected = cam.try_project_world_point(world_point, VIEWPORT)

    assert projected is not None
    assert projected.screen.x == pytest.approx(VIEWPORT_WIDTH * 0.5, abs=1.0e-6)
    assert projected.screen.y == pytest.approx(VIEWPORT_HEIGHT * 0.5, abs=1.0e-6)
    assert projected.view_point.y == pytest.approx(5.0, abs=1.0e-9)


def test_world_projection_rejects_missing_view_nonfinite_point_and_invalid_viewport():
    unattached = PerspectiveCameraComponent()
    assert unattached.try_project_world_point(Vec3(0.0, 5.0, 0.0), VIEWPORT) is None

    cam_entity, cam = build_basic_camera()
    assert cam.try_project_world_point(Vec3(float("nan"), 5.0, 0.0), VIEWPORT) is None
    assert cam.try_project_world_point(Vec3(0.0, 5.0, 0.0), Rect2(0.0, 0.0, 0.0, VIEWPORT_HEIGHT)) is None
