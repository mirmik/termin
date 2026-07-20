from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from tcgui.widgets.loader import UILoader
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
    def __init__(self) -> None:
        self.components: dict[str, type] = {}

    def register_builtin_components(self) -> list[str]:
        return []

    def register_component(self, name: str, component_type: type) -> None:
        self.components[name] = component_type

    def register_builtin_frame_passes(self) -> None:
        pass

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
    bootstrap_editor()
    resource_manager = _ResourceManager()

    try:
        register_editor_builtin_resources(resource_manager)
        assert resource_manager.components["EditorCameraUIController"] is EditorCameraUIController
    finally:
        shutdown_editor()


def test_editor_camera_ui_script_exposes_all_mode_buttons() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "termin-stdlib/python/termin/stdlib/resources/uiscript/editor_camera_ui.uiscript"

    text = script.read_text(encoding="utf-8")
    widget = UILoader().load_string(text)

    for name in (
        "colliders_btn",
        "navmesh_btn",
        "gizmo_orientation_btn",
        "wireframe_btn",
        "ortho_btn",
    ):
        assert widget.find(name) is not None


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
        def deserialize_data(self, data, scene) -> None:
            restored.append((data, scene))

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

    assert restored == [({"ortho_enabled": True}, "scene")]
