import json
from pathlib import Path

from termin_assets import PreLoadResult

from termin.player import project_runtime_support
from termin.player import project_settings


class RecordingResourceManager:
    def __init__(self) -> None:
        self.results: list[PreLoadResult] = []

    def register_file(self, result: PreLoadResult) -> None:
        self.results.append(result)


class RecordingPreloader:
    priority = 0

    def __init__(self, type_id: str = "shader") -> None:
        self.type_id = type_id
        self.paths: list[str] = []

    def preload(self, path: str) -> PreLoadResult:
        self.paths.append(path)
        return PreLoadResult(resource_type=self.type_id, path=path)


def test_source_project_settings_treat_missing_ignored_paths_as_empty(monkeypatch, tmp_path: Path):
    settings_dir = tmp_path / "project_settings"
    settings_dir.mkdir()
    (settings_dir / "project.json").write_text("{}", encoding="utf-8")
    warnings: list[str] = []
    monkeypatch.setattr(project_settings, "_log_warning", warnings.append)

    settings = project_settings.load_project_runtime_settings(tmp_path)

    assert settings.ignored_resource_paths == ()
    assert warnings == []


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


def test_source_asset_scan_does_not_allow_malformed_settings_to_ignore_project_root(monkeypatch, tmp_path: Path):
    project = tmp_path / "Game"
    keep = project / "Assets" / "Keep.shader"
    keep.parent.mkdir(parents=True)
    keep.write_text("@language slang\n", encoding="utf-8")

    settings_dir = project / "project_settings"
    settings_dir.mkdir()
    (settings_dir / "project.json").write_text(
        json.dumps({"ignored_resource_paths": [".", "../outside"]}),
        encoding="utf-8",
    )

    preloader = RecordingPreloader()
    monkeypatch.setattr(
        project_runtime_support,
        "create_asset_import_plugin_map",
        lambda: {".shader": preloader},
    )
    monkeypatch.setattr(
        project_runtime_support.DefaultResourceManager,
        "instance",
        staticmethod(RecordingResourceManager),
    )

    assert project_runtime_support.scan_project_assets(project, log_prefix="[Test]") == 1
    assert preloader.paths == [str(keep)]


def test_headless_asset_scan_skips_render_resources_and_keeps_gameplay_assets(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "Game"
    material = project / "Assets" / "Surface.material"
    audio = project / "Assets" / "Step.wav"
    material.parent.mkdir(parents=True)
    material.write_text("{}", encoding="utf-8")
    audio.write_bytes(b"wave")

    material_preloader = RecordingPreloader("material")
    audio_preloader = RecordingPreloader("audio_clip")
    monkeypatch.setattr(
        project_runtime_support,
        "create_asset_import_plugin_map",
        lambda: {".material": material_preloader, ".wav": audio_preloader},
    )
    manager = RecordingResourceManager()
    monkeypatch.setattr(
        project_runtime_support.DefaultResourceManager,
        "instance",
        staticmethod(lambda: manager),
    )

    loaded_count = project_runtime_support.scan_project_assets(
        project,
        log_prefix="[Test]",
        include_render_resources=False,
    )

    assert loaded_count == 1
    assert material_preloader.paths == []
    assert audio_preloader.paths == [str(audio)]
    assert [result.resource_type for result in manager.results] == ["audio_clip"]
