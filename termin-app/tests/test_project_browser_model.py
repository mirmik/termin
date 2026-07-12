from pathlib import Path

import pytest

from termin.editor_core.project_browser_model import (
    ProjectBrowserController,
    file_subtitle,
)
from termin.project.settings import ProjectSettings, ProjectSettingsManager


class _Operations:
    def __init__(self):
        self.calls = []
        self.refreshes = []

    def _record(self, action, path, refresh, *extra):
        self.calls.append((action, path, extra))
        self.refreshes.append(refresh)

    def create_directory(self, path, refresh):
        self._record("create-directory", path, refresh)

    def create_file(self, path, refresh):
        self._record("create-file", path, refresh)

    def create_material(self, path, refresh):
        self._record("create-material", path, refresh)

    def create_shader(self, path, refresh):
        self._record("create-shader", path, refresh)

    def create_component(self, path, refresh):
        self._record("create-component", path, refresh)

    def create_pipeline(self, path, refresh):
        self._record("create-pipeline", path, refresh)

    def create_prefab(self, path, refresh):
        self._record("create-prefab", path, refresh)

    def rename_item(self, path, refresh):
        self._record("rename", path, refresh)

    def delete_item(self, path, refresh):
        self._record("delete", path, refresh)

    def extract_glb(self, path, refresh, navigate):
        self._record("extract-glb", path, refresh, navigate)


def _project_tree(root: Path) -> None:
    (root / "Assets" / "Nested").mkdir(parents=True)
    (root / "Scripts").mkdir()
    (root / ".hidden").mkdir()
    (root / "tests").mkdir()
    (root / "scene.scene").write_text("{}", encoding="utf-8")
    (root / "mesh.stl").write_text("solid", encoding="utf-8")
    (root / "Assets" / "material.material").write_text("{}", encoding="utf-8")


def test_project_browser_navigation_filtering_selection_activation_drag_and_context(
    tmp_path: Path,
    monkeypatch,
):
    _project_tree(tmp_path)
    manager = ProjectSettingsManager()
    manager._settings = ProjectSettings(ignored_resource_paths=["tests"])
    monkeypatch.setattr(ProjectSettingsManager, "_instance", manager)
    selected = []
    activated = []
    clipboard = []
    controller = ProjectBrowserController(
        on_file_selected=selected.append,
        on_file_activated=activated.append,
        copy_text=clipboard.append,
    )

    root = controller.set_root(tmp_path)
    assert [entry.name for entry in root.entries] == [
        "Assets",
        "Scripts",
        "mesh.stl",
        "scene.scene",
    ]
    assert root.status == "2 directories | 2 files"
    assert file_subtitle(tmp_path / "mesh.stl") == "Mesh"
    assert not any(entry.name in {".hidden", "tests"} for entry in root.entries)

    scene_index = next(i for i, entry in enumerate(root.entries) if entry.name == "scene.scene")
    controller.select_entry(scene_index)
    controller.activate_entry(scene_index)
    assert selected == [tmp_path / "scene.scene"]
    assert activated == [tmp_path / "scene.scene"]
    assert controller.drag_payload(scene_index)["extension"] == ".scene"
    controller.execute_context_action("copy-path", scene_index)
    assert clipboard == [str((tmp_path / "scene.scene").resolve())]

    assets_index = next(i for i, entry in enumerate(root.entries) if entry.name == "Assets")
    nested = controller.activate_entry(assets_index)
    assert nested.selected_directory == tmp_path / "Assets"
    assert nested.breadcrumb[-1][0] == "Assets"
    assert controller.has_directory_children(tmp_path / "Assets")
    assert controller.go_up().selected_directory == tmp_path


def test_project_browser_rejects_roots_and_navigation_outside_project(tmp_path: Path):
    controller = ProjectBrowserController()
    with pytest.raises(NotADirectoryError):
        controller.set_root(tmp_path / "missing")
    controller.set_root(tmp_path)
    with pytest.raises(ValueError, match="outside"):
        controller.navigate(tmp_path.parent)


def test_project_browser_exposes_and_routes_mutation_actions(tmp_path: Path):
    _project_tree(tmp_path)
    glb = tmp_path / "actor.glb"
    glb.write_bytes(b"glb")
    operations = _Operations()
    controller = ProjectBrowserController(operations=operations)
    mutation_refreshes = []
    controller.set_mutation_refresh(lambda: mutation_refreshes.append(True))
    snapshot = controller.set_root(tmp_path)
    glb_index = next(i for i, entry in enumerate(snapshot.entries) if entry.path == glb)

    actions = {action.stable_id: action for action in controller.context_actions(glb_index)}
    assert actions["rename"].enabled
    assert actions["extract-glb"].enabled
    assert actions["create-material"].enabled

    controller.execute_context_action("rename", glb_index)
    controller.execute_context_action("extract-glb", glb_index)
    controller.execute_context_action("create-material", -1)
    controller.execute_directory_context_action("create-file", tmp_path / "Assets")
    assert [(action, path) for action, path, _extra in operations.calls] == [
        ("rename", glb),
        ("extract-glb", glb),
        ("create-material", tmp_path),
        ("create-file", tmp_path / "Assets"),
    ]
    operations.refreshes[-1]()
    assert mutation_refreshes == [True]
