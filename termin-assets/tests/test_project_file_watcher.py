from pathlib import Path
from typing import Set

from termin_assets import Asset, AssetRegistry, AssetRuntimeManager, PreLoadResult
from termin_assets import project_file_watcher as watcher_module
from termin_assets.plugin_preloader import PluginPreLoader
from termin_assets.project_file_watcher import FilePreLoader, ProjectFileWatcher


class RecordingRemovalPreLoader(FilePreLoader):
    def __init__(self, fail_on: set[str] | None = None) -> None:
        super().__init__(resource_manager=None)
        self.fail_on = fail_on or set()
        self.removed: list[str] = []

    @property
    def extensions(self) -> Set[str]:
        return {".asset"}

    @property
    def resource_type(self) -> str:
        return "asset"

    def on_file_removed(self, path: str) -> None:
        self.removed.append(path)
        if Path(path).name in self.fail_on:
            raise RuntimeError(f"failed to remove {path}")


def _queue_change(watcher: ProjectFileWatcher, path: Path, kind: str) -> None:
    with watcher._lock:
        watcher._pending_changes[str(path)] = kind


class DummyImportPlugin:
    type_id = "dummy"
    extensions = {".dummy"}
    priority = 10

    def preload(self, path: str) -> PreLoadResult:
        return PreLoadResult(resource_type=self.type_id, path=path, uuid="dummy-uuid")


class DummyRuntimePlugin:
    type_id = "dummy"

    def register(self, context, result: PreLoadResult) -> None:
        asset = Asset(name=context.name, source_path=result.path, uuid=result.uuid)
        context.resource_manager.register_runtime_asset(
            self.type_id,
            context.name,
            asset,
            source_path=result.path,
            uuid=result.uuid,
        )

    def reload(self, context, result: PreLoadResult) -> None:
        pass

    def unregister(self, context, result: PreLoadResult) -> None:
        context.resource_manager.unregister_runtime_asset(self.type_id, context.name)


def test_plugin_preloader_unregisters_runtime_asset_on_delete(tmp_path: Path) -> None:
    asset_path = tmp_path / "probe.dummy"
    asset_path.write_text("probe", encoding="utf-8")

    manager = AssetRuntimeManager()
    manager.register_runtime_asset_registry(
        "dummy",
        AssetRegistry(
            asset_class=Asset,
            uuid_registry=manager._assets_by_uuid,
            data_from_asset=lambda asset: asset,
        ),
    )
    manager.asset_type_plugins.register_runtime(DummyRuntimePlugin())

    watcher = ProjectFileWatcher()
    watcher.register_processor(PluginPreLoader(DummyImportPlugin(), manager))

    watcher._add_file(str(asset_path))
    assert manager.get_runtime_asset("dummy", "probe") is not None
    assert manager.get_asset_by_uuid("dummy-uuid") is not None

    asset_path.unlink()
    _queue_change(watcher, asset_path, "deleted")
    watcher.poll()

    assert manager.get_runtime_asset("dummy", "probe") is None
    assert manager.get_asset_by_uuid("dummy-uuid") is None


def test_poll_logs_failed_remove_and_processes_later_deletions(tmp_path: Path, monkeypatch) -> None:
    first_path = tmp_path / "first.asset"
    second_path = tmp_path / "second.asset"
    log_messages: list[str] = []

    monkeypatch.setattr(watcher_module.log, "exception", log_messages.append)

    processor = RecordingRemovalPreLoader(fail_on={"first.asset"})
    watcher = ProjectFileWatcher()
    watcher.register_processor(processor)
    watcher._watched_files.update({str(first_path), str(second_path)})
    _queue_change(watcher, first_path, "deleted")
    _queue_change(watcher, second_path, "deleted")

    watcher.poll()

    assert processor.removed == [str(first_path), str(second_path)]
    assert watcher.watched_files == set()
    assert log_messages == [f"[ProjectFileWatcher] Error removing {first_path}"]


def test_rescan_logs_failed_remove_and_processes_later_removed_files(tmp_path: Path, monkeypatch) -> None:
    first_path = tmp_path / "first.asset"
    second_path = tmp_path / "second.asset"
    log_messages: list[str] = []

    monkeypatch.setattr(watcher_module.log, "exception", log_messages.append)

    processor = RecordingRemovalPreLoader(fail_on={"first.asset"})
    watcher = ProjectFileWatcher()
    watcher.register_processor(processor)
    watcher._project_path = str(tmp_path)
    watcher._watched_files.update({str(first_path), str(second_path)})

    watcher.rescan()

    assert processor.removed == [str(first_path), str(second_path)]
    assert watcher.watched_files == set()
    assert log_messages == [f"[ProjectFileWatcher] Error removing {first_path}"]
