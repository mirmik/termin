from termin.project.settings import ProjectSettings, RenderSyncMode
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
    import termin._native as app_native

    assert "RenderSyncMode" not in dir(app_native)
    assert "set_render_sync_mode" not in dir(app_native)
    assert "get_render_sync_mode" not in dir(app_native)

    set_render_sync_mode(CRenderSyncMode.FLUSH)
    try:
        assert get_render_sync_mode() == CRenderSyncMode.FLUSH
        assert RenderSyncMode.FLUSH.to_c() == CRenderSyncMode.FLUSH
    finally:
        set_render_sync_mode(CRenderSyncMode.NONE)
