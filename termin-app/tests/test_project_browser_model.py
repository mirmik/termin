from pathlib import Path

import pytest

from termin.editor_core.project_browser_model import (
    ProjectBrowserController,
    file_subtitle,
)
from termin.project.settings import ProjectSettings, ProjectSettingsManager


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
