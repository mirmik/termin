from types import SimpleNamespace

import pytest
from termin.base._geom_native import Ray3, Rect2, Vec2, Vec3

from termin.editor_core.viewport_geometry_controller import ViewportGeometryController


class _Operations:
    def __init__(self):
        self.drops = []

    def drop_glb(self, path, parent, *, world_position):
        self.drops.append((path, parent, world_position))


def test_viewport_geometry_routes_project_glb_drop_to_scene_operations():
    operations = _Operations()
    scene_tree = SimpleNamespace(operations=operations)
    controller = ViewportGeometryController(
        get_camera=lambda: None,
        get_viewport_widget=lambda: None,
        get_interaction_system=lambda: None,
        get_editor_display=lambda: None,
        get_scene_tree_controller=lambda: scene_tree,
    )

    assert controller.drop_project_file("/project/model.glb", ".GLB", 20.0, 30.0)
    assert operations.drops[0][0:2] == ("/project/model.glb", None)
    assert not controller.drop_project_file("/project/albedo.png", ".png", 20.0, 30.0)


def _ray_controller(camera, width=640.0, height=480.0):
    return ViewportGeometryController(
        get_camera=lambda: camera,
        get_viewport_widget=lambda: SimpleNamespace(width=width, height=height),
        get_interaction_system=lambda: None,
        get_editor_display=lambda: None,
        get_scene_tree_controller=lambda: None,
    )


def _assert_screen_request(screen_point, viewport, *, width=640.0, height=480.0):
    assert type(screen_point) is Vec2
    assert (screen_point.x, screen_point.y) == (12.0, 34.0)
    assert type(viewport) is Rect2
    assert (viewport.x, viewport.y, viewport.width, viewport.height) == (0.0, 0.0, width, height)


def test_viewport_geometry_keeps_checked_ray_as_semantic_value():
    expected = Ray3(Vec3(1.0, 2.0, 3.0), Vec3(0.0, 1.0, 0.0))

    class Camera:
        entity = object()

        def try_screen_point_to_ray(self, screen_point, viewport):
            _assert_screen_request(screen_point, viewport)
            return expected

    ray = _ray_controller(Camera()).world_ray_from_viewport_point(12.0, 34.0)
    assert ray is expected


def test_viewport_geometry_returns_none_for_checked_projection_failure():
    class Camera:
        entity = object()

        def try_screen_point_to_ray(self, screen_point, viewport):
            _assert_screen_request(screen_point, viewport, width=0.0)
            return None

    assert _ray_controller(Camera(), width=0.0).world_ray_from_viewport_point(12.0, 34.0) is None


def test_viewport_geometry_does_not_hide_camera_api_regressions():
    class Camera:
        entity = object()

        def try_screen_point_to_ray(self, _screen_point, _viewport):
            raise AttributeError("camera binding regression")

    with pytest.raises(AttributeError, match="camera binding regression"):
        _ray_controller(Camera()).world_ray_from_viewport_point(12.0, 34.0)


def test_viewport_geometry_projects_through_checked_camera_api():
    point = Vec3(4.0, 5.0, 6.0)

    class Camera:
        entity = object()

        def try_project_world_point(self, world_point, viewport):
            assert world_point is point
            assert type(viewport) is Rect2
            assert (viewport.x, viewport.y, viewport.width, viewport.height) == (0.0, 0.0, 640.0, 480.0)
            return SimpleNamespace(screen=SimpleNamespace(x=123.5, y=234.5))

    assert _ray_controller(Camera()).project_world_point_to_viewport(point) == (123.5, 234.5)


def test_viewport_geometry_returns_none_for_checked_world_projection_failure():
    class Camera:
        entity = object()

        def try_project_world_point(self, _world_point, viewport):
            assert type(viewport) is Rect2
            assert (viewport.x, viewport.y, viewport.width, viewport.height) == (0.0, 0.0, 0.0, 480.0)
            return None

    assert _ray_controller(Camera(), width=0.0).project_world_point_to_viewport(Vec3.zero()) is None


@pytest.mark.parametrize(
    ("ray", "plane_origin", "plane_normal"),
    [
        (Ray3(Vec3(0.0, 0.0, 1.0), Vec3.unit_x()), Vec3.zero(), Vec3.unit_z()),
        (Ray3(Vec3(0.0, 0.0, 1.0), Vec3.unit_z()), Vec3.zero(), Vec3.unit_z()),
        (Ray3(Vec3(0.0, 0.0, 1.0), -Vec3.unit_z()), Vec3.zero(), Vec3.zero()),
        (Ray3(Vec3(0.0, 0.0, 1.0), -Vec3.unit_z()), Vec3(0.0, 0.0, float("nan")), Vec3.unit_z()),
    ],
)
def test_viewport_geometry_plane_pick_rejects_checked_misses(ray, plane_origin, plane_normal):
    class Camera:
        entity = object()

        def try_screen_point_to_ray(self, screen_point, viewport):
            _assert_screen_request(screen_point, viewport)
            return ray

    assert _ray_controller(Camera()).world_point_on_plane(12.0, 34.0, plane_origin, plane_normal) is None


def test_viewport_geometry_plane_pick_returns_forward_checked_intersection():
    expected = Vec3(1.0, 2.0, 0.0)

    class Camera:
        entity = object()

        def try_screen_point_to_ray(self, screen_point, viewport):
            _assert_screen_request(screen_point, viewport)
            return Ray3(Vec3(1.0, 2.0, 3.0), -Vec3.unit_z())

    assert _ray_controller(Camera()).world_point_on_plane(12.0, 34.0, Vec3.zero(), Vec3.unit_z()) == expected


@pytest.mark.parametrize("transformed_axis", [Vec3.unit_x(), Vec3(float("nan"), 0.0, 0.0)])
def test_viewport_geometry_entity_plane_rejects_degenerate_transformed_axes_before_projection(transformed_axis):
    class Transform:
        global_position = Vec3.zero()

        def transform_vector(self, _axis):
            return transformed_axis

    entity = SimpleNamespace(valid=lambda: True, transform=Transform())

    class Camera:
        entity = object()

        def try_screen_point_to_ray(self, _screen_point, _viewport):
            pytest.fail("degenerate entity plane must be rejected before camera projection")

    assert _ray_controller(Camera()).world_point_on_entity_local_oxy_plane(12.0, 34.0, entity) is None
