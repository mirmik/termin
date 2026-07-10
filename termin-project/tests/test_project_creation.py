import json

from termin.project import create_project, make_default_scene


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
