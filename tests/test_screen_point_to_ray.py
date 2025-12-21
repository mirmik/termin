import numpy as np
import pytest

from termin.visualization import Entity, Scene
from termin.visualization.core.camera import PerspectiveCameraComponent
from termin.geombase import Pose3
from termin.geombase._geom_native import Vec3
from termin.colliders import SphereCollider
from termin.geombase import GeneralPose3, Quat


def build_basic_camera():
    cam_entity = Entity(
        pose=Pose3(lin=np.array([0.0, 0.0, 0.0])),
        name="camera"
    )
    cam = PerspectiveCameraComponent()
    cam_entity.add_component(cam)
    return cam_entity, cam


def test_center_ray_direction_forward():
    w, h = 800, 600
    viewport = (0, 0, w, h)

    cam_entity, cam = build_basic_camera()
    ray = cam.screen_point_to_ray(w * 0.5, h * 0.5, viewport)

    # Project uses Y-forward convention (local +Y = forward)
    forward = np.array([0, 1, 0], dtype=float)
    dot = np.dot(ray.direction / np.linalg.norm(ray.direction), forward)
    assert dot > 0.99, f"Bad direction: {ray.direction}, dot={dot}"


def test_left_right_ray_symmetry():
    w, h = 800, 600
    viewport = (0, 0, w, h)

    cam_entity, cam = build_basic_camera()

    ray_left = cam.screen_point_to_ray(0, h * 0.5, viewport)
    ray_right = cam.screen_point_to_ray(w, h * 0.5, viewport)

    assert pytest.approx(ray_left.direction[0], rel=1e-3) == -ray_right.direction[0]
    assert pytest.approx(ray_left.direction[1], rel=1e-3) == ray_right.direction[1]
    assert pytest.approx(ray_left.direction[2], rel=1e-3) == ray_right.direction[2]


def test_top_bottom_symmetry():
    w, h = 800, 600
    viewport = (0, 0, w, h)

    cam_entity, cam = build_basic_camera()

    ray_top = cam.screen_point_to_ray(w * 0.5, 0, viewport)
    ray_bottom = cam.screen_point_to_ray(w * 0.5, h, viewport)

    # Y-forward convention: vertical screen maps to Z axis
    assert pytest.approx(ray_top.direction[2], rel=1e-3) == -ray_bottom.direction[2]
    assert pytest.approx(ray_top.direction[0], rel=1e-3) == ray_bottom.direction[0]


def test_raycast_center_hits_object():
    w, h = 800, 600
    viewport = (0, 0, w, h)

    scene = Scene()
    cam_entity, cam = build_basic_camera()
    scene.add(cam_entity)

    # Y-forward convention: object in front of camera is at +Y
    obj = Entity(pose=Pose3(lin=np.array([0.0, 5.0, 0.0])), name="obj")
    sphere = SphereCollider(1.0, GeneralPose3(Quat.identity(), Vec3(0.0, 5.0, 0.0)))

    from termin.colliders.collider_component import ColliderComponent
    obj.add_component(ColliderComponent(sphere))
    scene.add(obj)

    ray = cam.screen_point_to_ray(w * 0.5, h * 0.5, viewport)
    hit = scene.raycast(ray)

    assert hit is not None, "Raycast failed to hit the object"
    assert hit.entity.name == "obj"


def test_screen_edges_not_nan():
    w, h = 800, 600
    viewport = (0, 0, w, h)

    cam_entity, cam = build_basic_camera()

    edges = [
        (0, 0),
        (0, h),
        (w, 0),
        (w, h),
        (w // 2, 0),
        (0, h // 2),
    ]

    for x, y in edges:
        ray = cam.screen_point_to_ray(x, y, viewport)
        assert not np.isnan(ray.direction).any()
        assert not np.isnan(ray.origin).any()
