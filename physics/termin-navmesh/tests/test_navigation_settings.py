from termin.navmesh.settings import NavigationSettingsManager


def test_navigation_settings_ignores_legacy_project_json_area_names(tmp_path):
    settings_dir = tmp_path / "project_settings"
    settings_dir.mkdir()
    (settings_dir / "project.json").write_text(
        '{"navmesh_area_names": ["Legacy Walkable", "Legacy Area"]}',
        encoding="utf-8",
    )

    manager = NavigationSettingsManager()
    manager.set_project_path(tmp_path)

    assert manager.settings.navmesh_area_names[0] == "Walkable"
    assert manager.settings.navmesh_area_names[1] == ""


def test_navigation_settings_missing_area_names_use_defaults_without_legacy_import(tmp_path):
    settings_dir = tmp_path / "project_settings"
    settings_dir.mkdir()
    (settings_dir / "navigation.json").write_text('{"agent_types": []}', encoding="utf-8")
    (settings_dir / "project.json").write_text(
        '{"navmesh_area_names": ["Legacy Walkable", "Legacy Area"]}',
        encoding="utf-8",
    )

    manager = NavigationSettingsManager()
    manager.set_project_path(tmp_path)

    assert manager.settings.navmesh_area_names[0] == "Walkable"
    assert manager.settings.navmesh_area_names[1] == ""
