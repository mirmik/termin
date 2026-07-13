import json

import pytest

from termin.project import (
    InvalidProjectNameError,
    ProjectAlreadyExistsError,
    ProjectCreationError,
    create_project,
    create_project_file,
    make_default_scene,
)
from termin.project import creation as creation_module


def test_create_project_writes_manifest_settings_and_default_scene(tmp_path):
    project_file = create_project("Sample", str(tmp_path))
    project_dir = tmp_path / "Sample"
    settings_dir = project_dir / "project_settings"

    assert project_file == str(project_dir / "Sample.terminproj")
    assert json.loads((project_dir / "Sample.terminproj").read_text(encoding="utf-8")) == {
        "version": 1,
        "name": "Sample",
    }
    assert json.loads((settings_dir / "project.json").read_text(encoding="utf-8")) == {
        "render_sync_mode": "none",
    }

    navigation = json.loads((settings_dir / "navigation.json").read_text(encoding="utf-8"))
    assert navigation["agent_types"][0]["name"] == "Human"
    assert navigation["navmesh_area_names"][0] == "Walkable"
    assert len(navigation["navmesh_area_names"]) == 64

    editor_state = json.loads((settings_dir / ".editor_state.json").read_text(encoding="utf-8"))
    assert editor_state == {"last_scene": str(project_dir / "scene.scene")}

    scene = json.loads((project_dir / "scene.scene").read_text(encoding="utf-8"))
    assert scene["version"] == "1.0"
    assert [entity["name"] for entity in scene["scene"]["entities"]] == ["Cube", "Light", "Ground"]


def test_make_default_scene_returns_independent_scene_ids():
    first = make_default_scene()
    second = make_default_scene()

    assert first["scene"]["uuid"] != second["scene"]["uuid"]


def test_default_scene_uses_canonical_builtin_texture_uuids():
    serialized = json.dumps(make_default_scene())

    assert "5fb7972ad02ddfad" not in serialized
    assert "07151644d3bb92c7" not in serialized
    assert "__white_1x1__" in serialized
    assert "__normal_1x1__" in serialized


@pytest.mark.parametrize(
    "name",
    ["", ".", "..", "nested/project", r"nested\\project", "/absolute", "C:drive", "NUL"],
)
def test_create_project_rejects_non_leaf_or_portability_unsafe_names(tmp_path, name):
    with pytest.raises(InvalidProjectNameError):
        create_project(name, tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_create_project_does_not_overwrite_existing_directory(tmp_path):
    project_file = create_project("Sample", tmp_path)
    scene_file = tmp_path / "Sample" / "scene.scene"
    scene_file.write_text("preserve this scene", encoding="utf-8")

    with pytest.raises(ProjectAlreadyExistsError):
        create_project("Sample", tmp_path)

    assert project_file == str(tmp_path / "Sample" / "Sample.terminproj")
    assert scene_file.read_text(encoding="utf-8") == "preserve this scene"


def test_create_project_cleans_up_staging_when_template_generation_fails(tmp_path, monkeypatch):
    def fail_to_write_scene(_path: str) -> None:
        raise OSError("injected scene write failure")

    monkeypatch.setattr(creation_module, "write_default_scene", fail_to_write_scene)

    with pytest.raises(ProjectCreationError, match="injected scene write failure"):
        create_project("Broken", tmp_path)

    assert not (tmp_path / "Broken").exists()
    assert list(tmp_path.iterdir()) == []


def test_create_project_file_publishes_descriptor_without_overwriting(tmp_path):
    project_file = create_project_file("EditorProject", tmp_path)
    path = tmp_path / "EditorProject.terminproj"
    assert project_file == str(path)
    assert json.loads(path.read_text(encoding="utf-8")) == {"version": 1, "name": "EditorProject"}

    path.write_text("preserve this project", encoding="utf-8")
    with pytest.raises(ProjectAlreadyExistsError):
        create_project_file("EditorProject", tmp_path)

    assert path.read_text(encoding="utf-8") == "preserve this project"
