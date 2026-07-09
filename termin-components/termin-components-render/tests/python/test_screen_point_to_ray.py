import numpy as np
import pytest

from termin.scene import Entity
from termin.render_components.camera import PerspectiveCameraComponent
from termin.geombase import GeneralPose3, Pose3, Vec3


VIEWPORT_WIDTH = 800
VIEWPORT_HEIGHT = 600
VIEWPORT = (0, 0, VIEWPORT_WIDTH, VIEWPORT_HEIGHT)


def build_basic_camera():
    cam_entity = Entity(
        pose=GeneralPose3(lin=Vec3(0.0, 0.0, 0.0)),
        name="camera"
    )
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
    ray = cam.screen_point_to_ray(VIEWPORT_WIDTH * 0.5, VIEWPORT_HEIGHT * 0.5, VIEWPORT)

    # Project uses Y-forward convention (local +Y = forward)
    assert_valid_ray(ray, (0.0, 1.0, 0.0))


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
    ray = cam.screen_point_to_ray(x, y, VIEWPORT)

    assert_valid_ray(ray, expected_direction)
