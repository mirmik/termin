import json
from pathlib import Path

from termin_assets import PreLoadResult

from termin.player import project_runtime_support


class RecordingResourceManager:
    def __init__(self) -> None:
        self.results: list[PreLoadResult] = []

    def register_file(self, result: PreLoadResult) -> None:
        self.results.append(result)


class RecordingPreloader:
    priority = 0

    def __init__(self) -> None:
        self.paths: list[str] = []

    def preload(self, path: str) -> PreLoadResult:
        self.paths.append(path)
        return PreLoadResult(resource_type="shader", path=path)


def test_source_asset_scan_ignores_generated_and_project_ignored_paths(monkeypatch, tmp_path: Path):
    project = tmp_path / "Game"
    keep = project / "Assets" / "Keep.shader"
    generated = project / "dist" / "Game" / "site-packages" / "termin" / "Old.shader"
    ignored = project / "Ignored" / "Skip.shader"

    keep.parent.mkdir(parents=True)
    generated.parent.mkdir(parents=True)
    ignored.parent.mkdir(parents=True)
    keep.write_text("@language slang\n", encoding="utf-8")
    generated.write_text("#version 330 core\n", encoding="utf-8")
    ignored.write_text("@language slang\n", encoding="utf-8")

    settings_dir = project / "project_settings"
    settings_dir.mkdir()
    (settings_dir / "project.json").write_text(
        json.dumps({"ignored_resource_paths": ["Ignored"]}),
        encoding="utf-8",
    )

    preloader = RecordingPreloader()
    monkeypatch.setattr(
        project_runtime_support,
        "create_asset_import_plugin_map",
        lambda: {".shader": preloader},
    )

    manager = RecordingResourceManager()
    monkeypatch.setattr(
        project_runtime_support.DefaultResourceManager,
        "instance",
        staticmethod(lambda: manager),
    )

    loaded_count = project_runtime_support.scan_project_assets(project, log_prefix="[Test]")

    assert loaded_count == 1
    assert preloader.paths == [str(keep)]
    assert [result.path for result in manager.results] == [str(keep)]
