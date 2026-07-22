import json

from termin.project.settings import ProjectPlayerWindowSettings, ProjectSettings, RenderSyncMode
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
