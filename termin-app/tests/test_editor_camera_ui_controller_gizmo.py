from __future__ import annotations

from types import SimpleNamespace

from termin.bootstrap import bootstrap_editor, shutdown_editor
from termin.editor_core.editor_camera import EditorCameraManager
from termin.editor_core.editor_camera_ui_controller import EditorCameraUIController
from termin.editor_core.resource_loader import register_editor_builtin_resources
from termin.render import (
    RENDER_CATEGORY_ALL,
    RENDER_CATEGORY_COLLIDERS,
    RENDER_CATEGORY_NAVMESH,
)


class _TransformGizmo:
    def __init__(self) -> None:
        self.modes: list[str] = []

    def set_orientation_mode(self, mode: str) -> None:
        self.modes.append(mode)


class _Pass:
    def __init__(self, name: str) -> None:
        self.pass_name = name
        self.wireframe = False

    def to_python(self):
        return self


class _ResourceManager:
    def register_builtin_shaders(self) -> None:
        pass

    def register_builtin_textures(self) -> None:
        pass

    def register_builtin_materials(self) -> None:
        pass

    def register_builtin_meshes(self) -> list[str]:
        return []

    def register_builtin_pipelines(self) -> None:
        pass


def _runtime():
    passes = [_Pass("Color"), _Pass("Transparent")]
    pipeline = SimpleNamespace(passes=passes)
    render_target = SimpleNamespace(pipeline=pipeline)
    viewport = SimpleNamespace(render_target=render_target)
    camera = SimpleNamespace(
        render_category_mask=RENDER_CATEGORY_ALL,
        projection_type="perspective",
        viewport=viewport,
    )
    gizmo = _TransformGizmo()
    renders: list[bool] = []
    return camera, gizmo, renders, passes


def test_editor_builtin_resources_register_camera_ui_controller() -> None:
    from termin.scene import ComponentRegistry

    bootstrap_editor()
    resource_manager = _ResourceManager()

    try:
        register_editor_builtin_resources(resource_manager)
        assert (
            ComponentRegistry.instance().get_class("EditorCameraUIController")
            is EditorCameraUIController
        )
    finally:
        shutdown_editor()


def test_controller_applies_and_toggles_all_five_modes() -> None:
    camera, gizmo, renders, passes = _runtime()
    controller = EditorCameraUIController()

    assert controller.bind_runtime(
        camera=camera,
        gizmo=gizmo,
        request_render=lambda: renders.append(True),
    )
    assert camera.render_category_mask & RENDER_CATEGORY_COLLIDERS == 0
    assert camera.render_category_mask & RENDER_CATEGORY_NAVMESH
    assert camera.projection_type == "perspective"
    assert gizmo.modes == ["local"]

    controller.toggle_colliders()
    controller.toggle_navmesh()
    controller.toggle_wireframe()
    controller.toggle_projection()
    controller.toggle_gizmo_orientation()

    assert camera.render_category_mask & RENDER_CATEGORY_COLLIDERS
    assert camera.render_category_mask & RENDER_CATEGORY_NAVMESH == 0
    assert all(render_pass.wireframe for render_pass in passes)
    assert camera.projection_type == "orthographic"
    assert gizmo.modes == ["local", "world"]
    assert len(renders) == 5


def test_controller_resyncs_serialized_state_after_runtime_rebind() -> None:
    camera, gizmo, renders, passes = _runtime()
    controller = EditorCameraUIController()
    controller.colliders_enabled = True
    controller.navmesh_enabled = False
    controller.wireframe_enabled = True
    controller.ortho_enabled = True
    controller.gizmo_world_orientation_enabled = True

    controller.bind_runtime(
        camera=camera,
        gizmo=gizmo,
        request_render=lambda: renders.append(True),
    )

    assert camera.render_category_mask & RENDER_CATEGORY_COLLIDERS
    assert camera.render_category_mask & RENDER_CATEGORY_NAVMESH == 0
    assert all(render_pass.wireframe for render_pass in passes)
    assert camera.projection_type == "orthographic"
    assert gizmo.modes == ["world"]
    assert renders == []


def test_camera_state_migrates_legacy_overlay_controller_fields() -> None:
    restored = []

    class ComponentRef:
        def __init__(self) -> None:
            self.source_id = "generated-controller-id"

        def deserialize_data(self, data, scene) -> None:
            restored.append((self.source_id, data, scene))

    class TestEntity:
        def __init__(self, name: str, children=()) -> None:
            self.name = name
            self.transform = SimpleNamespace(
                children=[SimpleNamespace(entity=child) for child in children]
            )

        def get_tc_component(self, component_type: str):
            if self.name == "camera" and component_type == "EditorCameraUIController":
                return ComponentRef()
            return None

    camera = TestEntity("camera")
    manager = EditorCameraManager()
    manager.editor_entities = TestEntity("EditorEntities", (camera,))
    manager._scene = "scene"
    old_state = {
        "editor_ui": [
            {
                "type": "EditorCameraUIController",
                "data": {"ortho_enabled": True},
            }
        ]
    }

    manager._deserialize_editor_entities_components(old_state)

    assert restored == [
        ("generated-controller-id", {"ortho_enabled": True}, "scene")
    ]


def test_camera_state_restores_component_envelope_identity() -> None:
    restored = []

    class ComponentRef:
        source_id = "generated-camera-id"

        def deserialize_data(self, data, scene) -> None:
            restored.append((self.source_id, data, scene))

    component = ComponentRef()

    class TestEntity:
        name = "camera"
        transform = SimpleNamespace(children=[])

        def get_tc_component(self, component_type: str):
            return component if component_type == "CameraComponent" else None

    manager = EditorCameraManager()
    manager.editor_entities = TestEntity()
    manager._scene = "scene"
    manager._deserialize_editor_entities_components(
        {
            "camera": [
                {
                    "source_id": "stable-camera-id",
                    "type": "CameraComponent",
                    "data": {"near_clip": 0.25},
                }
            ]
        }
    )

    assert restored == [("stable-camera-id", {"near_clip": 0.25}, "scene")]


def test_editor_camera_components_keep_source_identity_across_recreation() -> None:
    from termin.scene import TcScene

    bootstrap_editor()
    scene = TcScene.create("editor-camera-identity")
    manager = EditorCameraManager()
    try:
        register_editor_builtin_resources(_ResourceManager())
        manager.attach_to_scene(scene)
        initial = manager.get_camera_data()
        assert initial is not None
        initial_components = initial["editor_entities"]["camera"]
        initial_ids = {
            component["type"]: component["source_id"]
            for component in initial_components
        }
        assert initial_ids["CameraComponent"]
        assert initial_ids["OrbitCameraController"]
        assert initial_ids["EditorCameraUIController"]

        manager.detach_from_scene()
        manager.attach_to_scene(scene)
        manager.set_camera_data(initial)
        restored = manager.get_camera_data()
        assert restored is not None
        restored_ids = {
            component["type"]: component["source_id"]
            for component in restored["editor_entities"]["camera"]
        }

        assert restored_ids == initial_ids
    finally:
        manager.detach_from_scene()
        scene.destroy()
        shutdown_editor()
