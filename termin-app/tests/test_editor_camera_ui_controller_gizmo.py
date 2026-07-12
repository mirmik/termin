from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from tcgui.widgets.loader import UILoader
from termin.editor_core.editor_camera_ui_controller import EditorCameraUIController
from termin.editor_core.resource_loader import register_editor_builtin_resources
from termin.render import RENDER_CATEGORY_ALL, RENDER_CATEGORY_COLLIDERS, RENDER_CATEGORY_NAVMESH


class _IconButton:
    def __init__(self) -> None:
        self.active = False
        self.icon = ""
        self.tooltip = ""


class _TransformGizmo:
    def __init__(self) -> None:
        self.modes: list[str] = []

    def set_orientation_mode(self, mode: str) -> None:
        self.modes.append(mode)


class _InteractionSystem:
    def __init__(self) -> None:
        self.transform_gizmo = _TransformGizmo()
        self.update_count = 0
        self.on_request_update = self._request_update

    def _request_update(self) -> None:
        self.update_count += 1


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


def test_editor_builtin_resources_register_camera_ui_controller() -> None:
    resource_manager = _ResourceManager()

    register_editor_builtin_resources(resource_manager)

    assert resource_manager.components["EditorCameraUIController"] is EditorCameraUIController


def test_editor_camera_ui_script_exposes_gizmo_orientation_button() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "termin-stdlib/python/termin/stdlib/resources/uiscript/editor_camera_ui.uiscript"

    text = script.read_text(encoding="utf-8")
    widget = UILoader().load_string(text)

    assert widget.find("gizmo_orientation_btn") is not None
    assert widget.find("wireframe_btn") is not None
    assert widget.find("ortho_btn") is not None
    assert "name: gizmo_orientation_btn" in text
    assert text.index("name: gizmo_orientation_btn") < text.index("name: wireframe_btn")
    assert text.index("name: gizmo_orientation_btn") < text.index("name: ortho_btn")


def test_editor_camera_ui_controller_toggles_gizmo_orientation(monkeypatch) -> None:
    interaction_system = _InteractionSystem()

    class _EditorInteractionSystem:
        @staticmethod
        def instance():
            return interaction_system

    monkeypatch.setitem(
        sys.modules,
        "termin.editor._editor_native",
        SimpleNamespace(EditorInteractionSystem=_EditorInteractionSystem),
    )

    button = _IconButton()
    controller = EditorCameraUIController()
    controller._gizmo_orientation_btn = button

    controller._apply_gizmo_orientation()

    assert interaction_system.transform_gizmo.modes == ["local"]
    assert button.active is False
    assert button.icon == "L"

    controller._on_gizmo_orientation_click()

    assert controller.gizmo_world_orientation_enabled is True
    assert interaction_system.transform_gizmo.modes == ["local", "world"]
    assert interaction_system.update_count == 1
    assert button.active is True
    assert button.icon == "G"


def test_editor_camera_ui_controller_updates_camera_render_category_mask(monkeypatch) -> None:
    interaction_system = _InteractionSystem()

    class _EditorInteractionSystem:
        @staticmethod
        def instance():
            return interaction_system

    monkeypatch.setitem(
        sys.modules,
        "termin.editor._editor_native",
        SimpleNamespace(EditorInteractionSystem=_EditorInteractionSystem),
    )

    controller = EditorCameraUIController()
    camera = SimpleNamespace(render_category_mask=RENDER_CATEGORY_ALL, viewport=None)
    colliders_button = _IconButton()
    navmesh_button = _IconButton()
    controller._camera_component = camera
    controller._colliders_btn = colliders_button
    controller._navmesh_btn = navmesh_button

    controller._sync_button_states()

    assert camera.render_category_mask & RENDER_CATEGORY_COLLIDERS == 0
    assert camera.render_category_mask & RENDER_CATEGORY_NAVMESH
    assert colliders_button.active is False
    assert navmesh_button.active is True

    controller._on_colliders_click()
    assert camera.render_category_mask & RENDER_CATEGORY_COLLIDERS
    assert colliders_button.active is True
    assert interaction_system.update_count == 1

    controller._on_navmesh_click()
    assert camera.render_category_mask & RENDER_CATEGORY_NAVMESH == 0
    assert navmesh_button.active is False
    assert interaction_system.update_count == 2
