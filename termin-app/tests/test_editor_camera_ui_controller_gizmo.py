from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from tcgui.widgets.loader import UILoader
from termin.editor_tcgui.editor_camera_ui_controller import EditorCameraUIController


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
