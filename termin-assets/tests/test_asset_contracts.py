from termin_assets import (
    Asset,
    AssetRegistry,
    AssetTypeRegistry,
    DataAsset,
    Identifiable,
    PreLoadResult,
    ResourceHandle,
    build_import_plugin_extension_map,
    get_uuid_from_spec,
    register_default_import_asset_plugins,
    register_default_runtime_asset_plugins,
    register_import_plugins_from_entry_points,
    read_spec_file,
    write_spec_file,
)
import termin_assets.plugin_discovery as plugin_discovery


def test_asset_core_classes_are_exported() -> None:
    assert Identifiable is not None
    assert Asset is not None
    assert DataAsset is not None
    assert AssetRegistry is not None
    assert ResourceHandle is not None


def test_resource_handle_can_lookup_assets_by_uuid() -> None:
    asset = Asset(name="probe", uuid="probe-uuid")

    class FakeResourceManager:
        def get_probe_asset_by_uuid(self, uuid: str):
            return asset if uuid == asset.uuid else None

    class ProbeHandle(ResourceHandle[object, Asset]):
        _asset_by_uuid_getter = "get_probe_asset_by_uuid"

    from termin_assets import set_resource_manager_factory

    set_resource_manager_factory(FakeResourceManager)
    try:
        handle = ProbeHandle.from_uuid("probe-uuid")
        missing = ProbeHandle.from_uuid("missing")
    finally:
        set_resource_manager_factory(None)

    assert handle.get_asset() is asset
    assert missing.get_asset() is None


class DummyPlugin:
    type_id = "dummy"
    extensions = {".dummy"}
    priority = 20

    def preload(self, path: str) -> PreLoadResult:
        return PreLoadResult(resource_type=self.type_id, path=path)

    def register(self, context, result: PreLoadResult) -> None:
        pass

    def reload(self, context, result: PreLoadResult) -> None:
        pass


def test_registry_finds_plugin_by_type_and_extension() -> None:
    registry = AssetTypeRegistry()
    plugin = DummyPlugin()

    registry.register(plugin)

    assert registry.get("dummy") is plugin
    assert registry.get_runtime("dummy") is plugin
    assert registry.get_import("dummy") is plugin
    assert registry.get_for_extension(".DUMMY") == [plugin]


def test_registry_replaces_import_plugin_extension_entries_by_type_id() -> None:
    registry = AssetTypeRegistry()
    first_plugin = DummyPlugin()
    second_plugin = DummyPlugin()

    registry.register_import(first_plugin)
    registry.register_import(second_plugin)

    assert registry.get_import("dummy") is second_plugin
    assert registry.get_for_extension(".dummy") == [second_plugin]


class RuntimeOnlyPlugin:
    type_id = "runtime_only"

    def register(self, context, result: PreLoadResult) -> None:
        pass

    def reload(self, context, result: PreLoadResult) -> None:
        pass


class ImportOnlyPlugin:
    type_id = "runtime_only"
    extensions = {".runtime-only"}
    priority = 5

    def preload(self, path: str) -> PreLoadResult:
        return PreLoadResult(resource_type=self.type_id, path=path)


def test_registry_keeps_runtime_and_import_plugins_separate() -> None:
    registry = AssetTypeRegistry()
    runtime_plugin = RuntimeOnlyPlugin()
    import_plugin = ImportOnlyPlugin()

    registry.register_runtime(runtime_plugin)
    registry.register_import(import_plugin)

    assert registry.get_runtime("runtime_only") is runtime_plugin
    assert registry.get_import("runtime_only") is import_plugin
    assert registry.get_for_extension(".runtime-only") == [import_plugin]


def test_spec_file_helpers_prefer_meta_and_migrate_legacy_spec(tmp_path) -> None:
    asset_path = tmp_path / "probe.obj"
    asset_path.write_text("", encoding="utf-8")
    spec_path = tmp_path / "probe.obj.spec"
    spec_path.write_text('{"uuid": "legacy"}', encoding="utf-8")

    assert read_spec_file(str(asset_path)) == {"uuid": "legacy"}
    assert get_uuid_from_spec(str(asset_path)) == "legacy"

    assert write_spec_file(str(asset_path), {"uuid": "meta"})
    assert read_spec_file(str(asset_path)) == {"uuid": "meta"}
    assert not spec_path.exists()


class _EntryPoint:
    name = "external_dummy"

    def load(self):
        return DummyPlugin


def test_import_plugin_entry_point_discovery(monkeypatch) -> None:
    registry = AssetTypeRegistry()

    def fake_entry_points(group: str):
        if group == "termin.asset_import_plugins":
            return [_EntryPoint()]
        return []

    monkeypatch.setattr(plugin_discovery, "entry_points", fake_entry_points)

    register_import_plugins_from_entry_points(registry)

    assert registry.get_import("dummy") is not None
    assert registry.get_for_extension(".dummy")[0].type_id == "dummy"


def test_default_plugin_helpers_load_entry_points(monkeypatch) -> None:
    registry = AssetTypeRegistry()

    def fake_entry_points(group: str):
        if group in {"termin.asset_import_plugins", "termin.asset_runtime_plugins"}:
            return [_EntryPoint()]
        return []

    monkeypatch.setattr(plugin_discovery, "entry_points", fake_entry_points)

    register_default_runtime_asset_plugins(registry)
    assert registry.get_runtime("dummy") is not None
    assert registry.get_import("dummy") is None

    register_default_import_asset_plugins(registry)

    assert registry.get_import("dummy") is not None
    extension_map = build_import_plugin_extension_map(registry)
    assert extension_map[".dummy"].type_id == "dummy"
