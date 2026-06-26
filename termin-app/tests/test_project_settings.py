from termin.project.settings import ProjectPlayerWindowSettings, ProjectSettings, RenderSyncMode
from termin.render import (
    RenderSyncMode as CRenderSyncMode,
    get_render_sync_mode,
    set_render_sync_mode,
)


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
            }
        }
    )

    assert settings.player_window == ProjectPlayerWindowSettings(
        width=1600,
        height=900,
        fullscreen=False,
    )


def test_project_settings_invalid_player_window_fields_use_defaults() -> None:
    settings = ProjectSettings.from_dict(
        {
            "player_window": {
                "width": 0,
                "height": True,
                "fullscreen": "no",
            }
        }
    )

    assert settings.player_window == ProjectPlayerWindowSettings()