import importlib.util
from pathlib import Path

import pytest


def _load_binding_class():
    path = (
        Path(__file__).resolve().parents[2]
        / "termin-app/termin/editor_core/primary_render_scene_binding.py"
    )
    spec = importlib.util.spec_from_file_location(
        "primary_render_scene_binding_under_test",
        path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PrimaryRenderSceneBinding


PrimaryRenderSceneBinding = _load_binding_class()


class _RenderConnector:
    def __init__(self) -> None:
        self.attached = {"Editor", "Preview", "Tools"}
        self.events: list[tuple] = []
        self.failures: dict[tuple[str, str], int] = {}

    def fail_once(self, operation: str, scene_name: str) -> None:
        self.failures[(operation, scene_name)] = 1

    def _fails(self, operation: str, scene_name: str) -> bool:
        key = (operation, scene_name)
        remaining = self.failures.get(key, 0)
        if remaining == 0:
            return False
        self.failures[key] = remaining - 1
        return True

    def sync_scene_render_state(self, scene_name: str) -> bool:
        self.events.append(("sync", scene_name))
        return not self._fails("sync", scene_name)

    def attach_scene_to_render(self, scene_name: str) -> bool:
        self.events.append(("attach", scene_name))
        if self._fails("attach", scene_name):
            return False
        self.attached.add(scene_name)
        return True

    def detach_scene_from_render(
        self,
        scene_name: str,
        *,
        save_state: bool,
    ) -> bool:
        self.events.append(("detach", scene_name, save_state))
        if self._fails("detach", scene_name):
            return False
        self.attached.discard(scene_name)
        return True


def test_primary_render_binding_rebinds_only_its_owned_scene() -> None:
    connector = _RenderConnector()
    binding = PrimaryRenderSceneBinding(connector, "Editor")

    binding.sync_current()
    assert binding.rebind("Game") is True

    assert binding.scene_name == "Game"
    assert connector.attached == {"Game", "Preview", "Tools"}
    assert connector.events == [
        ("sync", "Editor"),
        ("attach", "Game"),
        ("detach", "Editor", False),
    ]


def test_primary_render_binding_leaves_current_scene_on_attach_failure() -> None:
    connector = _RenderConnector()
    connector.fail_once("attach", "Game")
    binding = PrimaryRenderSceneBinding(connector, "Editor")

    with pytest.raises(RuntimeError, match="attach render scene 'Game'"):
        binding.rebind("Game")

    assert binding.scene_name == "Editor"
    assert connector.attached == {"Editor", "Preview", "Tools"}
    assert binding.may_reference("Game") is False


def test_primary_render_binding_rolls_back_failed_old_scene_detach() -> None:
    connector = _RenderConnector()
    connector.fail_once("detach", "Editor")
    binding = PrimaryRenderSceneBinding(connector, "Editor")

    with pytest.raises(RuntimeError, match="detach render scene 'Editor'"):
        binding.rebind("Game")

    assert binding.scene_name == "Editor"
    assert connector.attached == {"Editor", "Preview", "Tools"}
    assert binding.may_reference("Game") is False
    assert connector.events == [
        ("attach", "Game"),
        ("detach", "Editor", False),
        ("attach", "Editor"),
        ("detach", "Game", False),
    ]
