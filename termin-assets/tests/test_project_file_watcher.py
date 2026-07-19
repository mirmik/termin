from pathlib import Path
from typing import Set

from termin_assets import (
    Asset,
    AssetIdentityPolicy,
    AssetRegistry,
    AssetRuntimeManager,
    PreLoadResult,
)
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


class RecordingLifecyclePreLoader(RecordingRemovalPreLoader):
    def __init__(self) -> None:
        super().__init__()
        self.initial_added: list[str] = []
        self.added: list[str] = []

    def on_file_added(self, path: str) -> None:
        self.added.append(path)

    def on_initial_file_added(self, path: str) -> None:
        self.initial_added.append(path)
        super().on_initial_file_added(path)


def _queue_change(watcher: ProjectFileWatcher, path: Path, kind: str) -> None:
    with watcher._lock:
        watcher._pending_changes[str(path)] = kind


class DummyImportPlugin:
    type_id = "dummy"
    extensions = {".dummy"}
    priority = 10

    def preload(self, path: str) -> PreLoadResult:
        return PreLoadResult(resource_type=self.type_id, path=path, uuid="dummy-uuid")


class SidecarDummyImportPlugin:
    type_id = "sidecar_dummy"
    extensions = {".sidecar"}
    priority = 10

    def preload(self, path: str) -> PreLoadResult:
        return PreLoadResult(
            resource_type=self.type_id,
            path=path,
            identity_policy=AssetIdentityPolicy.GENERATE_SIDECAR,
        )


class SidecarUuidImportPlugin(SidecarDummyImportPlugin):
    def __init__(self, uuid: object) -> None:
        self.uuid = uuid

    def preload(self, path: str) -> PreLoadResult:
        result = super().preload(path)
        result.uuid = self.uuid
        return result


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
        context.resource_manager.unregister_runtime_asset_by_uuid(self.type_id, context.uuid)


def test_plugin_preloader_assigns_one_persistent_sidecar_uuid(tmp_path: Path) -> None:
    asset_path = tmp_path / "probe.sidecar"
    asset_path.write_text("probe", encoding="utf-8")
    preloader = PluginPreLoader(SidecarDummyImportPlugin(), resource_manager=None)

    first = preloader.preload(str(asset_path))
    second = preloader.preload(str(asset_path))

    assert first is not None
    assert second is not None
    assert first.uuid
    assert second.uuid == first.uuid
    assert first.spec_data == {"uuid": first.uuid}
    assert second.spec_data == first.spec_data
    assert (tmp_path / "probe.sidecar.meta").read_text(encoding="utf-8") == (f'{{\n  "uuid": "{first.uuid}"\n}}\n')


def test_plugin_preloader_rejects_invalid_existing_sidecar_uuid(
    tmp_path: Path,
    caplog,
) -> None:
    asset_path = tmp_path / "probe.sidecar"
    asset_path.write_text("probe", encoding="utf-8")
    meta_path = tmp_path / "probe.sidecar.meta"
    meta_path.write_text('{"uuid": 42}', encoding="utf-8")
    preloader = PluginPreLoader(SidecarDummyImportPlugin(), resource_manager=None)

    assert preloader.preload(str(asset_path)) is None
    assert meta_path.read_text(encoding="utf-8") == '{"uuid": 42}'
    assert "Invalid asset UUID in metadata" in caplog.text


def test_plugin_preloader_validates_plugin_uuid_against_sidecar(
    tmp_path: Path,
    monkeypatch,
) -> None:
    asset_path = tmp_path / "probe.sidecar"
    asset_path.write_text("probe", encoding="utf-8")
    meta_path = tmp_path / "probe.sidecar.meta"
    meta_path.write_text('{"uuid": "persistent-uuid"}', encoding="utf-8")
    preloader = PluginPreLoader(SidecarUuidImportPlugin("different-uuid"), resource_manager=None)
    log_messages: list[str] = []
    monkeypatch.setattr("termin_assets.plugin_preloader.log.error", log_messages.append)

    assert preloader.preload(str(asset_path)) is None
    assert len(log_messages) == 1
    assert "Import UUID does not match persistent metadata" in log_messages[0]


def test_plugin_preloader_rejects_non_object_sidecar(tmp_path: Path, caplog) -> None:
    asset_path = tmp_path / "probe.sidecar"
    asset_path.write_text("probe", encoding="utf-8")
    meta_path = tmp_path / "probe.sidecar.meta"
    meta_path.write_text("[]", encoding="utf-8")
    preloader = PluginPreLoader(SidecarDummyImportPlugin(), resource_manager=None)

    assert preloader.preload(str(asset_path)) is None
    assert "Asset meta file must contain a JSON object" in caplog.text


def test_plugin_preloader_unregisters_runtime_asset_on_delete(tmp_path: Path) -> None:
    asset_path = tmp_path / "probe.dummy"
    asset_path.write_text("probe", encoding="utf-8")

    manager = AssetRuntimeManager()
    manager.register_runtime_asset_registry(
        "dummy",
        AssetRegistry(
            asset_class=Asset,
            asset_store=manager._asset_store,
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


def test_rescan_keeps_existing_files_without_readding_them(tmp_path: Path) -> None:
    asset_path = tmp_path / "stable.asset"
    asset_path.write_text("stable", encoding="utf-8")

    processor = RecordingLifecyclePreLoader()
    watcher = ProjectFileWatcher()
    watcher.register_processor(processor)
    watcher._project_path = str(tmp_path)

    watcher._scan_directory(str(tmp_path))
    assert processor.initial_added == [str(asset_path)]
    assert processor.added == [str(asset_path)]

    watcher.rescan()

    assert watcher.watched_files == {str(asset_path)}
    assert processor.initial_added == [str(asset_path)]
    assert processor.added == [str(asset_path)]
    assert processor.removed == []


def test_rescan_adds_new_files_discovered_since_previous_scan(tmp_path: Path) -> None:
    first_path = tmp_path / "first.asset"
    first_path.write_text("first", encoding="utf-8")

    processor = RecordingLifecyclePreLoader()
    watcher = ProjectFileWatcher()
    watcher.register_processor(processor)
    watcher._project_path = str(tmp_path)

    watcher._scan_directory(str(tmp_path))

    second_path = tmp_path / "second.asset"
    second_path.write_text("second", encoding="utf-8")
    watcher.rescan()

    assert watcher.watched_files == {str(first_path), str(second_path)}
    assert processor.initial_added == [str(first_path), str(second_path)]
    assert processor.added == [str(first_path), str(second_path)]
    assert processor.removed == []
