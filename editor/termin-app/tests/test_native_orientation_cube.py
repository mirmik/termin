from math import atan2, hypot
from types import SimpleNamespace

import pytest

from termin.editor_core.orientation_cube_geometry import build_orientation_cube
from termin.editor_native.orientation_cube import NativeOrientationCube
from termin.geombase import Quat, Vec3
from termin.gui_native import (
    EventResult, OverlayAnchor, PointerEvent, PointerEventType, Rect, Size,
    tc_ui_document_create, tc_ui_document_destroy,
)
from termin.render_components import OrbitCameraController, ViewDirection
from termin.visual_scene import tc_visual_scene3d_create, tc_visual_scene3d_destroy


class _Controller:
    def __init__(self):
        self.snaps = []
        self.radius = 7.0

    def snap_view(self, direction):
        self.snaps.append(direction)


class _Camera:
    def __init__(self):
        self.entity = _Entity()
        self.axis_distances = []
        self.leave_count = 0

    def enter_axis_view(self, distance):
        self.axis_distances.append(distance)

    def leave_axis_view(self):
        self.leave_count += 1


class _Entity:
    def __init__(self):
        self.transform = SimpleNamespace(global_rotation=Quat.identity())
        self.controller = _Controller()

    def get_component(self, component_type):
        assert component_type is OrbitCameraController
        return self.controller


@pytest.fixture
def cube_rig():
    document = tc_ui_document_create()
    composition = document.create_overlay_layout("test-viewport")
    background_scene = tc_visual_scene3d_create()
    background = document.create_scene_view3d(background_scene)
    scene_events = []
    background.set_fallback_pointer_handler(
        lambda event, ray: scene_events.append(event.type) or True
    )
    assert composition.add_child(background.widget, OverlayAnchor.Fill)
    assert document.add_root(composition.handle)
    renders = []
    viewport = SimpleNamespace(
        document=document, composition=composition,
        camera=_Camera(),
        _request_render=lambda: renders.append(True),
    )
    cube = NativeOrientationCube(viewport)
    document.layout_roots(Rect(0.0, 0.0, 800.0, 600.0))
    rig = SimpleNamespace(
        cube=cube, viewport=viewport, document=document, background=background,
        scene_events=scene_events, renders=renders,
    )
    try:
        yield rig
    finally:
        cube.close()
        background.set_fallback_pointer_handler(None)
        background.detach_scene()
        tc_ui_document_destroy(document)
        tc_visual_scene3d_destroy(background_scene)


def _aim(rig, direction):
    x, y, z = direction
    azimuth = atan2(x, -y) if x or y else 0.0
    elevation = atan2(z, hypot(x, y))
    rig.viewport.camera.entity.transform.global_rotation = (
        Quat.from_axis_angle(Vec3(0.0, 0.0, 1.0), azimuth)
        * Quat.from_axis_angle(Vec3(1.0, 0.0, 0.0), -elevation)
    )
    # Camera providers run at render time. These input-only tests install the
    # exact same camera without creating a graphics device.
    camera = rig.cube._provide_camera(Size(160.0, 160.0))
    rig.cube.view.set_camera_provider(None)
    rig.cube.view.camera = camera


def _center(rig):
    bounds = rig.cube.view.widget.bounds_in_document
    return bounds.x + bounds.width / 2, bounds.y + bounds.height / 2


def _pointer(rig, kind, position, button=0):
    event = PointerEvent()
    event.type = kind
    event.x, event.y = position
    event.button = button
    return rig.document.dispatch_pointer_event(event)


@pytest.mark.parametrize("patch", build_orientation_cube(), ids=lambda patch: patch.key)
def test_real_scene_hits_and_activates_all_26_directions(cube_rig, patch):
    rig = cube_rig
    _aim(rig, patch.direction)
    center = _center(rig)
    ray = rig.cube.view.world_ray(*center)
    assert ray is not None
    hit = rig.cube.scene.hit_test(ray)
    assert hit is not None
    assert hit.item.handle == rig.cube._items[patch.key].handle
    assert _pointer(rig, PointerEventType.Down, center) == EventResult.Handled
    assert _pointer(rig, PointerEventType.Up, center) == EventResult.Handled
    assert rig.viewport.camera.entity.controller.snaps == [ViewDirection[patch.key]]
    if sum(value != 0 for value in patch.direction) == 1:
        assert rig.viewport.camera.axis_distances == [7.0]
        assert rig.viewport.camera.leave_count == 0
    else:
        assert rig.viewport.camera.axis_distances == []
        assert rig.viewport.camera.leave_count == 1
    assert PointerEventType.Down not in rig.scene_events
    assert rig.renders


def test_cube_remains_anchored_at_top_right_after_resize(cube_rig):
    rig = cube_rig
    before = rig.cube.view.widget.bounds_in_document
    assert before.width == pytest.approx(160.0)
    assert before.height == pytest.approx(160.0)
    rig.document.layout_roots(Rect(0.0, 0.0, 1100.0, 750.0))
    after = rig.cube.view.widget.bounds_in_document
    assert after.x - before.x == pytest.approx(300.0)
    assert after.y == pytest.approx(before.y)
    assert after.width == before.width
    assert after.height == before.height
    _aim(rig, (0.0, -1.0, 0.0))
    _pointer(rig, PointerEventType.Down, _center(rig))
    _pointer(rig, PointerEventType.Up, _center(rig))
    assert rig.viewport.camera.entity.controller.snaps == [ViewDirection.SOUTH]


def test_capture_release_outside_cube_does_not_snap_or_reach_scene(cube_rig):
    rig = cube_rig
    _aim(rig, (0.0, -1.0, 0.0))
    assert _pointer(rig, PointerEventType.Down, _center(rig)) == EventResult.Handled
    assert _pointer(rig, PointerEventType.Move, (20.0, 350.0)) == EventResult.Handled
    assert _pointer(rig, PointerEventType.Up, (20.0, 350.0)) == EventResult.Handled
    assert rig.viewport.camera.entity.controller.snaps == []
    assert PointerEventType.Down not in rig.scene_events
    assert PointerEventType.Up not in rig.scene_events
    assert rig.cube._pressed is None


def test_outside_cube_input_reaches_viewport_scene(cube_rig):
    rig = cube_rig
    _aim(rig, (0.0, -1.0, 0.0))
    assert _pointer(rig, PointerEventType.Down, (20.0, 350.0)) == EventResult.Handled
    assert _pointer(rig, PointerEventType.Up, (20.0, 350.0)) == EventResult.Handled
    assert PointerEventType.Down in rig.scene_events
    assert PointerEventType.Up in rig.scene_events
    assert rig.viewport.camera.entity.controller.snaps == []


def test_right_button_does_not_activate_cube(cube_rig):
    rig = cube_rig
    _aim(rig, (0.0, -1.0, 0.0))
    _pointer(rig, PointerEventType.Down, _center(rig), button=1)
    _pointer(rig, PointerEventType.Up, _center(rig), button=1)
    assert rig.viewport.camera.entity.controller.snaps == []
    assert rig.cube._pressed is None


def test_rebinding_routes_to_new_controller_and_close_releases_owned_objects(cube_rig):
    rig = cube_rig
    old_controller = rig.viewport.camera.entity.controller
    count = rig.document.live_widget_count
    rig.cube.unbind_camera()
    assert not rig.cube.view.widget.enabled
    rig.viewport.camera = _Camera()
    rig.cube.rebind_camera()
    assert rig.cube.view.widget.enabled
    assert rig.document.live_widget_count == count
    _aim(rig, (0.0, 0.0, 1.0))
    _pointer(rig, PointerEventType.Down, _center(rig))
    _pointer(rig, PointerEventType.Up, _center(rig))
    assert old_controller.snaps == []
    assert rig.viewport.camera.entity.controller.snaps == [ViewDirection.TOP]
    # Exercise teardown with the live provider installed.
    rig.cube.view.set_camera_provider(rig.cube._provide_camera)
    scene = rig.cube.scene
    root = rig.cube.root
    rig.cube.close()
    rig.cube.close()
    assert not scene.valid
    assert not root.alive
    assert rig.document.live_widget_count == 2  # composition and background
    assert rig.cube._controller is None
    assert rig.cube._camera is None
    assert not rig.cube._items
