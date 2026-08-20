import json

import pytest

from termin.project import (
    InvalidProjectNameError,
    ProjectAlreadyExistsError,
    ProjectCreationError,
    create_project,
    create_project_file,
    initialize_project,
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
        "application": {
            "id": "org.termin.builds.sample",
            "label": "Sample",
            "version_code": 1,
            "version_name": "0.1.0",
        },
    }

    navigation = json.loads((settings_dir / "navigation.json").read_text(encoding="utf-8"))
    assert navigation["agent_types"][0]["name"] == "Human"
    assert navigation["navmesh_area_names"][0] == "Walkable"
    assert len(navigation["navmesh_area_names"]) == 64

    editor_state = json.loads((settings_dir / ".editor_state.json").read_text(encoding="utf-8"))
    assert editor_state == {"last_scene": "scene.scene"}

    scene = json.loads((project_dir / "scene.scene").read_text(encoding="utf-8"))
    assert scene["version"] == "1.0"
    assert [entity["name"] for entity in scene["scene"]["entities"]] == [
        "Cube",
        "Light",
        "Ground",
        "Camera",
    ]


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


def test_default_scene_has_attachable_runtime_viewport():
    scene = make_default_scene()["scene"]
    camera = next(entity for entity in scene["entities"] if entity["name"] == "Camera")
    assert camera["components"][0]["type"] == "CameraComponent"

    render_mount = scene["extensions"]["render_mount"]
    assert render_mount["viewport_configs"] == [
        {
            "name": "MainViewport",
            "display_name": "Main",
            "region": [0.0, 0.0, 1.0, 1.0],
            "depth": 0,
            "input_mode": "simple",
            "block_input_in_editor": False,
            "render_target": {"name": "MainTarget"},
            "enabled": True,
        }
    ]
    assert render_mount["render_target_configs"][0]["camera_uuid"] == camera["uuid"]
    assert render_mount["render_target_configs"][0]["pipeline_name"] == "Default"


@pytest.mark.parametrize(
    ("entity_name", "mesh_uuid", "mesh_name"),
    [
        ("Cube", "00000000-0000-0000-0003-000000000001", "Cube"),
        ("Ground", "00000000-0000-0000-0003-000000000003", "Plane"),
    ],
)
def test_default_mesh_entities_use_canonical_typed_resource_components(
    entity_name,
    mesh_uuid,
    mesh_name,
):
    entities = make_default_scene()["scene"]["entities"]
    entity = next(item for item in entities if item["name"] == entity_name)

    assert [component["type"] for component in entity["components"]] == [
        "MeshComponent",
        "MeshRenderer",
    ]
    mesh_data = entity["components"][0]["data"]
    renderer_data = entity["components"][1]["data"]
    assert mesh_data["mesh"] == {
        "uuid": mesh_uuid,
        "name": mesh_name,
        "type": "uuid",
        "kind": "tc_mesh",
    }
    assert "mesh" not in renderer_data
    assert renderer_data["material"] == {
        "uuid": "00000000-0001-0000-0001-000000000003",
        "name": "NormalizedPBR",
        "type": "uuid",
        "kind": "tc_material",
    }


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


def test_initialize_project_writes_into_existing_directory_and_preserves_unrelated_files(
    tmp_path,
):
    project_dir = tmp_path / "Sample"
    project_dir.mkdir()
    readme = project_dir / "README.md"
    readme.write_text("keep me", encoding="utf-8")

    project_file = initialize_project(project_dir)

    assert project_file == str(project_dir / "Sample.terminproj")
    assert json.loads((project_dir / "Sample.terminproj").read_text(encoding="utf-8")) == {
        "version": 1,
        "name": "Sample",
    }
    assert (project_dir / "project_settings" / "project.json").is_file()
    assert (project_dir / "scene.scene").is_file()
    assert readme.read_text(encoding="utf-8") == "keep me"


def test_initialize_project_accepts_explicit_name(tmp_path):
    project_dir = tmp_path / "directory-name"
    project_dir.mkdir()

    project_file = initialize_project(project_dir, "Game")

    assert project_file == str(project_dir / "Game.terminproj")


@pytest.mark.parametrize("conflict", ["Existing.terminproj", "scene.scene", "project_settings"])
def test_initialize_project_does_not_overwrite_project_paths(tmp_path, conflict):
    project_dir = tmp_path / "Sample"
    project_dir.mkdir()
    path = project_dir / conflict
    if conflict == "project_settings":
        path.mkdir()
    else:
        path.write_text("preserve", encoding="utf-8")

    with pytest.raises(ProjectAlreadyExistsError):
        initialize_project(project_dir)

    assert path.exists()
    assert not (project_dir / "Sample.terminproj").exists()


def test_initialize_project_rolls_back_published_targets_on_failure(tmp_path, monkeypatch):
    project_dir = tmp_path / "Sample"
    project_dir.mkdir()
    original_publish = creation_module._publish_staged_path
    publish_count = 0

    def fail_second_publish(staging_path, target_path):
        nonlocal publish_count
        publish_count += 1
        if publish_count == 2:
            raise ProjectCreationError("injected publication failure")
        original_publish(staging_path, target_path)

    monkeypatch.setattr(creation_module, "_publish_staged_path", fail_second_publish)

    with pytest.raises(ProjectCreationError, match="injected publication failure"):
        initialize_project(project_dir)

    assert list(project_dir.iterdir()) == []


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
