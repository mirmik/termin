import pytest

from termin.geombase import Mat44, OrbitCamera, ProjectedScreenPoint, Ray3, Rect2, Vec2, Vec3


def test_orbit_camera_returns_canonical_matrices():
    camera = OrbitCamera()

    assert isinstance(camera.view_matrix(), Mat44)
    assert isinstance(camera.projection_matrix(4.0 / 3.0), Mat44)
    assert isinstance(camera.mvp(4.0 / 3.0), Mat44)


def test_orbit_camera_screen_ray_returns_canonical_ray():
    camera = OrbitCamera()

    ray = camera.screen_ray(
        Vec2(400.0, 300.0),
        Rect2(0.0, 0.0, 800.0, 600.0),
    )

    assert isinstance(ray, Ray3)
    assert ray.direction.norm() == pytest.approx(1.0)


def test_orbit_camera_try_screen_ray_returns_none_for_invalid_viewport():
    camera = OrbitCamera()

    ray = camera.try_screen_ray(
        Vec2(0.0, 0.0),
        Rect2(0.0, 0.0, 0.0, 600.0),
    )

    assert ray is None


def test_orbit_camera_screen_ray_raises_for_invalid_viewport():
    camera = OrbitCamera()

    with pytest.raises(ValueError, match="viewport must be finite and have positive width and height"):
        camera.screen_ray(Vec2(0.0, 0.0), Rect2(0.0, 0.0, 0.0, 600.0))


def test_orbit_camera_world_projection_returns_canonical_semantic_value():
    camera = OrbitCamera()
    viewport = Rect2(0.0, 0.0, 800.0, 600.0)

    projected = camera.try_project_world_point(camera.target, viewport)

    assert isinstance(projected, ProjectedScreenPoint)
    assert projected.screen.x == pytest.approx(400.0)
    assert projected.screen.y == pytest.approx(300.0)
    assert 0.0 < projected.depth < 1.0
    assert projected.view_point.z == pytest.approx(-camera.distance)


def test_orbit_camera_world_projection_rejects_invalid_input():
    camera = OrbitCamera()

    assert camera.try_project_world_point(
        Vec3(float("nan"), 0.0, 0.0),
        Rect2(0.0, 0.0, 800.0, 600.0),
    ) is None
    assert camera.try_project_world_point(
        Vec3(0.0, 0.0, 0.0),
        Rect2(0.0, 0.0, 0.0, 600.0),
    ) is None
