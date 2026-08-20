import json

import pytest

from termin.project.application_identity import ProjectApplicationIdentity
from termin.project.ignored_paths import project_ignored_roots
from termin.project.settings import (
    ProjectPlayerWindowSettings,
    ProjectSettings,
    ProjectSettingsManager,
    RenderSyncMode,
)
from termin.project.world_controller_selection import (
    ProjectWorldControllerSelection,
    WorldControllerSelectionError,
)
from termin.player.project_settings import ProjectRuntimeSettings
from termin.project_build.desktop_build import _load_project_settings
from termin.render import (
    PROJECT_RENDER_PHASE_CAPACITY,
    RenderSyncMode as CRenderSyncMode,
    get_render_sync_mode,
    set_render_sync_mode,
)


def test_project_render_phase_registry_is_indexed_and_explicit() -> None:
    names = [""] * PROJECT_RENDER_PHASE_CAPACITY
    names[3] = "gameplay_overlay"
    settings = ProjectSettings.from_dict({"render_phase_names": names})

    assert settings.render_phase_names[3] == "gameplay_overlay"
    assert settings.to_dict()["render_phase_names"] == names


def test_project_render_phase_registry_rejects_duplicates_and_builtins() -> None:
    duplicate = [""] * PROJECT_RENDER_PHASE_CAPACITY
    duplicate[0] = duplicate[1] = "overlay"
    builtin = [""] * PROJECT_RENDER_PHASE_CAPACITY
    builtin[0] = "normal"

    for names in (duplicate, builtin):
        try:
            ProjectSettings.from_dict({"render_phase_names": names})
        except ValueError:
            pass
        else:
            raise AssertionError("invalid render phase registry must be rejected")


def test_project_settings_normalizes_ignored_resource_paths() -> None:
    settings = ProjectSettings.from_dict(
        {
            "ignored_resource_paths": [
                "Generated",
                "Generated",
                "Nested\\Cache",
                "",
                ".",
                "../outside",
                "/absolute",
                42,
            ],
        }
    )

    assert settings.ignored_resource_paths == [
        "Generated",
        "Nested/Cache",
    ]


def test_project_settings_serializes_ignored_resource_paths() -> None:
    settings = ProjectSettings(ignored_resource_paths=["Generated", "Cache"])

    assert settings.to_dict()["ignored_resource_paths"] == ["Generated", "Cache"]


def test_project_ignored_roots_include_private_service_and_generated_paths(tmp_path) -> None:
    project_root = tmp_path / "Game"
    settings = ProjectSettings(
        build_output_dir="out",
        ignored_resource_paths=["Generated"],
    )

    assert project_ignored_roots(project_root, settings) == (
        (project_root / ".termin").resolve(),
        (project_root / ".venv").resolve(),
        (project_root / "out").resolve(),
        (project_root / "Generated").resolve(),
    )


def test_ignored_resource_path_contract_is_shared_by_editor_build_and_player(tmp_path) -> None:
    values = [
        "Assets",
        "Nested\\Cache",
        "Assets",
        ".",
        "..",
        "../outside",
        "Nested/../outside",
        "/absolute",
        "",
        42,
    ]
    expected = ["Assets", "Nested/Cache"]
    data = {"ignored_resource_paths": values}

    editor_settings = ProjectSettings.from_dict(data)
    player_settings = ProjectRuntimeSettings.from_dict(data)

    project = tmp_path / "Game"
    settings_path = project / "project_settings" / "project.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(json.dumps(data), encoding="utf-8")
    build_settings = _load_project_settings(project)

    assert editor_settings.ignored_resource_paths == expected
    assert list(player_settings.ignored_resource_paths) == expected
    assert build_settings.ignored_resource_paths == expected


def test_render_sync_mode_runtime_binding_belongs_to_render_package() -> None:
    set_render_sync_mode(CRenderSyncMode.FLUSH)
    try:
        assert get_render_sync_mode() == CRenderSyncMode.FLUSH
        assert RenderSyncMode.FLUSH.to_c() == CRenderSyncMode.FLUSH
    finally:
        set_render_sync_mode(CRenderSyncMode.NONE)


def test_project_settings_normalizes_player_window() -> None:
    settings = ProjectSettings.from_dict(
        {
            "player_window": {
                "width": 1600,
                "height": 900,
                "fullscreen": False,
                "vsync": False,
            }
        }
    )

    assert settings.player_window == ProjectPlayerWindowSettings(
        width=1600,
        height=900,
        fullscreen=False,
        vsync=False,
    )


def test_project_settings_invalid_player_window_fields_use_defaults() -> None:
    settings = ProjectSettings.from_dict(
        {
            "player_window": {
                "width": 0,
                "height": True,
                "fullscreen": "no",
                "vsync": "sometimes",
            }
        }
    )

    assert settings.player_window == ProjectPlayerWindowSettings()


def test_project_application_identity_defaults_and_round_trips() -> None:
    first = ProjectSettings.from_dict({}, project_name="First Game")
    second = ProjectSettings.from_dict({}, project_name="Second Game")

    assert first.application == ProjectApplicationIdentity(
        application_id="org.termin.builds.first.game",
        label="First Game",
        version_code=1,
        version_name="0.1.0",
    )
    assert first.application.application_id != second.application.application_id

    custom = ProjectSettings.from_dict(
        {
            "application": {
                "id": "com.example.product",
                "label": "Example Product",
                "version_code": 42,
                "version_name": "2.3.1-beta",
            }
        },
        project_name="Ignored Default",
    )
    assert ProjectSettings.from_dict(
        custom.to_dict(),
        project_name="Ignored Default",
    ).application == custom.application


def test_project_world_controller_absence_and_selection_round_trip() -> None:
    absent = ProjectSettings.from_dict({})
    explicit_null = ProjectSettings.from_dict({"world_controller": None})

    assert absent.world_controller is None
    assert explicit_null.world_controller is None
    assert absent.to_dict()["world_controller"] is None

    selected = ProjectSettings.from_dict(
        {
            "world_controller": {
                "module": " avalon.game ",
                "type": " avalon.GameDirector ",
            }
        }
    )
    assert selected.world_controller == ProjectWorldControllerSelection(
        module="avalon.game",
        type_name="avalon.GameDirector",
    )
    assert ProjectSettings.from_dict(selected.to_dict()).world_controller == (
        selected.world_controller
    )


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (False, "world_controller must be null or an object"),
        ({}, "missing required field"),
        ({"module": "game"}, "missing required field"),
        ({"type": "Director"}, "missing required field"),
        (
            {"module": "game", "type": "Director", "config": {}},
            "unexpected field",
        ),
        ({"module": 7, "type": "Director"}, "world_controller.module"),
        ({"module": "game", "type": None}, "world_controller.type"),
        ({"module": " ", "type": "Director"}, "world_controller.module"),
        ({"module": "game", "type": ""}, "world_controller.type"),
    ],
)
def test_project_world_controller_rejects_malformed_explicit_selection(
    value: object,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        ProjectSettings.from_dict({"world_controller": value})


def test_project_settings_manager_sets_and_clears_world_controller(tmp_path) -> None:
    manager = ProjectSettingsManager()
    manager.set_project_path(tmp_path)
    selection = ProjectWorldControllerSelection(
        module="avalon.game",
        type_name="avalon.GameDirector",
    )

    manager.set_world_controller(selection)

    settings_path = tmp_path / "project_settings" / "project.json"
    assert json.loads(settings_path.read_text(encoding="utf-8"))["world_controller"] == {
        "module": "avalon.game",
        "type": "avalon.GameDirector",
    }
    reloaded = ProjectSettingsManager()
    reloaded.set_project_path(tmp_path)
    assert reloaded.settings.world_controller == selection

    reloaded.set_world_controller(None)
    assert json.loads(settings_path.read_text(encoding="utf-8"))["world_controller"] is None


def test_project_settings_manager_does_not_turn_malformed_selection_into_null(
    tmp_path,
) -> None:
    settings_path = tmp_path / "project_settings" / "project.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(
        json.dumps(
            {
                "world_controller": {
                    "module": "avalon.game",
                }
            }
        ),
        encoding="utf-8",
    )

    manager = ProjectSettingsManager()
    with pytest.raises(WorldControllerSelectionError, match="missing required field"):
        manager.set_project_path(tmp_path)


def test_last_scene_is_stored_relative_to_project_root(tmp_path) -> None:
    project_root = tmp_path / "Game"
    scene = project_root / "Scenes" / "Main.scene"
    scene.parent.mkdir(parents=True)
    scene.write_text("{}", encoding="utf-8")
    manager = ProjectSettingsManager()
    manager.set_project_path(project_root)

    manager.set_last_scene(str(scene))

    state_path = project_root / "project_settings" / ".editor_state.json"
    assert json.loads(state_path.read_text(encoding="utf-8"))["last_scene"] == (
        "Scenes/Main.scene"
    )
    assert manager.get_last_scene() == str(scene.resolve())


def test_legacy_absolute_last_scene_migrates_to_current_checkout(tmp_path) -> None:
    old_root = tmp_path / "old-checkout" / "Game"
    old_scene = old_root / "Scenes" / "Main.scene"
    old_scene.parent.mkdir(parents=True)
    old_scene.write_text("{}", encoding="utf-8")

    project_root = tmp_path / "new-checkout" / "Game"
    current_scene = project_root / "Scenes" / "Main.scene"
    current_scene.parent.mkdir(parents=True)
    current_scene.write_text("{}", encoding="utf-8")
    state_path = project_root / "project_settings" / ".editor_state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps({"last_scene": str(old_scene)}),
        encoding="utf-8",
    )
    manager = ProjectSettingsManager()
    manager.set_project_path(project_root)

    assert manager.get_last_scene() == str(current_scene.resolve())
    assert json.loads(state_path.read_text(encoding="utf-8"))["last_scene"] == (
        "Scenes/Main.scene"
    )


def test_last_scene_outside_project_is_not_persisted(tmp_path) -> None:
    project_root = tmp_path / "Game"
    project_root.mkdir()
    outside_scene = tmp_path / "Outside.scene"
    outside_scene.write_text("{}", encoding="utf-8")
    manager = ProjectSettingsManager()
    manager.set_project_path(project_root)

    manager.set_last_scene(str(outside_scene))

    assert not (project_root / "project_settings" / ".editor_state.json").exists()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("id", "one-segment", "application.id"),
        ("id", "com.example.bad-id", "application.id"),
        ("label", " ", "application.label"),
        ("version_code", 0, "application.version_code"),
        ("version_code", True, "application.version_code"),
        ("version_name", "", "application.version_name"),
    ],
)
def test_project_application_identity_rejects_invalid_values(
    field: str,
    value: object,
    message: str,
) -> None:
    data = {
        "id": "com.example.product",
        "label": "Product",
        "version_code": 1,
        "version_name": "1.0",
    }
    data[field] = value

    with pytest.raises(ValueError, match=message):
        ProjectSettings.from_dict({"application": data}, project_name="Product")
