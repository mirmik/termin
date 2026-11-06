import pytest

from termin.geombase import AABB, CameraProjection, Mat44, OrbitCamera, ProjectedScreenPoint, Ray3, Rect2, Vec2, Vec3


def test_orbit_camera_returns_canonical_matrices():
    camera = OrbitCamera()

    assert isinstance(camera.view_matrix(), Mat44)
    assert isinstance(camera.projection_matrix(4.0 / 3.0), Mat44)
    assert isinstance(camera.mvp(4.0 / 3.0), Mat44)


@pytest.mark.parametrize("projection", [CameraProjection.Perspective, CameraProjection.Orthographic])
@pytest.mark.parametrize("coordinate", [0.0, 1e12])
def test_fit_single_point_keeps_camera_projectable(projection, coordinate):
    camera = OrbitCamera()
    camera.projection_type = projection
    point = Vec3(coordinate, -coordinate, coordinate)
    camera.fit_bounds(AABB(point, point))
    projected = camera.try_project_world_point(point, Rect2(0, 0, 800, 600))
    assert projected is not None
    assert projected.screen.x == pytest.approx(400, abs=0.1)
    assert projected.screen.y == pytest.approx(300, abs=0.1)
    assert 0 < projected.depth < 1


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
    assert projected.view_point.y == pytest.approx(camera.distance)
    assert projected.view_point.z == pytest.approx(0.0, abs=1.0e-9)


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


def test_orthographic_camera_exposes_shared_projection_and_isometric_preset():
    camera = OrbitCamera()
    camera.set_isometric()
    assert camera.projection_type == CameraProjection.Orthographic
    camera.fit_bounds(AABB(Vec3(-1.0, -1.0, -1.0), Vec3(1.0, 1.0, 1.0)), aspect=0.5)
    original_size = camera.ortho_size
    original_distance = camera.distance
    camera.zoom(0.5)
    assert camera.ortho_size == pytest.approx(original_size * 0.5)
    assert camera.distance == original_distance

    viewport = Rect2(0.0, 0.0, 400.0, 800.0)
    center = camera.try_project_world_point(camera.target, viewport)
    lengths = []
    for axis in (Vec3(1.0, 0.0, 0.0), Vec3(0.0, 1.0, 0.0), Vec3(0.0, 0.0, 1.0)):
        point = camera.try_project_world_point(camera.target + axis, viewport)
        lengths.append((point.screen - center.screen).norm())
    assert lengths[0] == pytest.approx(lengths[1])
    assert lengths[0] == pytest.approx(lengths[2])


def test_orthographic_zoom_preserves_sub_unit_sizes():
    camera = OrbitCamera()
    camera.projection_type = CameraProjection.Orthographic
    camera.ortho_size = 0.001
    camera.zoom(0.9)
    assert camera.ortho_size == pytest.approx(0.0009)
