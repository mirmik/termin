from __future__ import annotations
from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy

from types import SimpleNamespace

from termin.editor_native.camera_overlay import NativeEditorCameraOverlayProjection
from termin.gui_native import TcDocument, EventResult, PointerEvent, PointerEventType, Rect


class _Controller:
    def __init__(self) -> None:
        self.colliders_enabled = False
        self.navmesh_enabled = True
        self.wireframe_enabled = False
        self.ortho_enabled = False
        self.gizmo_world_orientation_enabled = False
        self.bindings = []
        self.unbind_count = 0

    def bind_runtime(self, **capabilities) -> None:
        self.bindings.append(capabilities)

    def unbind_runtime(self) -> None:
        self.unbind_count += 1

    def toggle_colliders(self) -> None:
        self.colliders_enabled = not self.colliders_enabled

    def toggle_navmesh(self) -> None:
        self.navmesh_enabled = not self.navmesh_enabled

    def toggle_wireframe(self) -> None:
        self.wireframe_enabled = not self.wireframe_enabled

    def toggle_projection(self) -> None:
        self.ortho_enabled = not self.ortho_enabled

    def toggle_gizmo_orientation(self) -> None:
        self.gizmo_world_orientation_enabled = not self.gizmo_world_orientation_enabled


class _Entity:
    def __init__(self, controller) -> None:
        self.controller = controller

    def get_component(self, _component_type):
        return self.controller


class _Viewport:
    def __init__(self, document: TcDocument, controller) -> None:
        self.document = document
        self.camera = SimpleNamespace(entity=_Entity(controller))
        self.interaction = SimpleNamespace(transform_gizmo=object())
        self._request_render = lambda: None
        self.loaded = None

    def install_overlay(self, name: str, loaded) -> None:
        assert name == "editor-camera"
        self.loaded = loaded

    def remove_overlay(self, name: str) -> bool:
        assert name == "editor-camera"
        if self.loaded is None:
            return False
        self.loaded.close()
        self.loaded = None
        return True


def test_native_camera_overlay_loads_shared_script_binds_actions_and_closes() -> None:
    document = tc_ui_document_create()
    controller = _Controller()
    viewport = _Viewport(document, controller)

    projection = NativeEditorCameraOverlayProjection.create(viewport)
    assert viewport.loaded is not None
    assert controller.bindings[-1]["camera"] is viewport.camera
    assert viewport.loaded.named("navmesh_btn").active

    colliders = viewport.loaded.named("colliders_btn")
    colliders.widget.bounds = Rect(0.0, 0.0, 26.0, 26.0)
    pointer = PointerEvent()
    pointer.x = 4.0
    pointer.y = 4.0
    pointer.type = PointerEventType.Down
    assert colliders.widget.dispatch_pointer_event(pointer) == EventResult.Handled
    pointer.type = PointerEventType.Up
    assert colliders.widget.dispatch_pointer_event(pointer) == EventResult.Handled
    assert controller.colliders_enabled
    assert colliders.active

    projection.close()
    assert controller.unbind_count == 1
    assert viewport.loaded is None
    assert document.live_widget_count == 0
    tc_ui_document_destroy(document)


def test_native_camera_overlay_rebinds_actions_to_new_scene_controller() -> None:
    document = tc_ui_document_create()
    first = _Controller()
    viewport = _Viewport(document, first)
    projection = NativeEditorCameraOverlayProjection.create(viewport)

    second = _Controller()
    viewport.camera = SimpleNamespace(entity=_Entity(second))
    projection.rebind_camera()
    colliders = viewport.loaded.named("colliders_btn")
    colliders.widget.bounds = Rect(0.0, 0.0, 26.0, 26.0)
    pointer = PointerEvent()
    pointer.x = 4.0
    pointer.y = 4.0
    pointer.type = PointerEventType.Down
    colliders.widget.dispatch_pointer_event(pointer)
    pointer.type = PointerEventType.Up
    colliders.widget.dispatch_pointer_event(pointer)

    assert not first.colliders_enabled
    assert second.colliders_enabled
    assert first.unbind_count == 1
    projection.close()

    recreated = NativeEditorCameraOverlayProjection.create(viewport)
    assert second.bindings
    recreated.close()
    assert document.live_widget_count == 0
    tc_ui_document_destroy(document)
