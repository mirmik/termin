from termin.editor_core.project_settings_model import (
    ProjectSettingsController,
    ProjectSettingsSnapshot,
    RENDER_SYNC_MODES,
)
from termin.project.settings import ProjectSettingsManager


def _manager(tmp_path):
    manager = ProjectSettingsManager()
    manager.set_project_path(tmp_path)
    return manager


def test_project_settings_controller_persists_normalizes_and_notifies(tmp_path):
    manager = _manager(tmp_path)
    resource_changes = []
    render_changes = []
    controller = ProjectSettingsController(
        manager,
        on_resource_settings_changed=lambda: resource_changes.append(True),
        on_render_settings_changed=lambda: render_changes.append(True),
    )
    initial = controller.load()
    next_mode = next(mode for mode in RENDER_SYNC_MODES if mode != initial.render_sync_mode)

    saved = controller.save(
        ProjectSettingsSnapshot(
            render_sync_mode=next_mode,
            build_output_dir=" generated\\desktop ",
            player_width=1920,
            player_height=1080,
            player_fullscreen=False,
            player_vsync=False,
            ignored_resource_paths=(" cache ", "cache", "generated/assets"),
            render_phase_names=initial.render_phase_names,
        )
    )

    assert saved.render_sync_mode == next_mode
    assert saved.build_output_dir == "generated/desktop"
    assert saved.player_width == 1920
    assert saved.player_height == 1080
    assert not saved.player_fullscreen
    assert not saved.player_vsync
    assert saved.ignored_resource_paths == ("cache", "generated/assets")
    assert resource_changes == [True]
    assert render_changes == [True]
    assert (tmp_path / "project_settings" / "project.json").is_file()


def test_project_settings_controller_player_window_does_not_notify_resources(tmp_path):
    resource_changes = []
    controller = ProjectSettingsController(
        _manager(tmp_path),
        on_resource_settings_changed=lambda: resource_changes.append(True),
    )

    snapshot = controller.set_player_window(800, 600, False, False)

    assert (
        snapshot.player_width,
        snapshot.player_height,
        snapshot.player_fullscreen,
        snapshot.player_vsync,
    ) == (
        800,
        600,
        False,
        False,
    )
    assert resource_changes == []


def test_project_settings_controller_requires_open_project():
    controller = ProjectSettingsController(ProjectSettingsManager())

    try:
        controller.load()
    except RuntimeError as error:
        assert str(error) == "no project is open"
    else:
        raise AssertionError("missing project must be rejected")
