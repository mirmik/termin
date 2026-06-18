from pathlib import Path

from termin_assets import (
    Asset,
    AssetRegistry,
    AssetRuntimeManager,
    AssetTypeRegistry,
    DataAsset,
    EmbeddedAssetSpec,
    Identifiable,
    PreLoadResult,
    ResourceHandle,
    build_import_plugin_extension_map,
    get_resource_manager,
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
    assert EmbeddedAssetSpec is not None
    assert AssetRegistry is not None
    assert ResourceHandle is not None


class MemoryAsset(DataAsset[str]):
    def _parse_content(self, content: bytes | str) -> str | None:
        return str(content)


def test_data_asset_can_store_lazy_runtime_data_without_private_mutation() -> None:
    asset = MemoryAsset(name="probe")

    asset.set_runtime_data("declared-handle", loaded=False)

    assert asset.cached_data == "declared-handle"
    assert not asset.is_loaded

    asset.set_runtime_data("ready-data")

    assert asset.cached_data == "ready-data"
    assert asset.data == "ready-data"
    assert asset.is_loaded


def test_runtime_manager_get_or_create_embedded_asset_uses_runtime_registry() -> None:
    manager = AssetRuntimeManager()
    registry = AssetRegistry(
        asset_class=MemoryAsset,
        uuid_registry=manager._assets_by_uuid,
        data_from_asset=lambda asset: asset.data,
    )
    manager.register_runtime_asset_registry("memory", registry)

    parent = MemoryAsset(name="bundle", uuid="bundle-uuid")
    child = manager.get_or_create_embedded_asset(
        EmbeddedAssetSpec(
            type_id="memory",
            name="bundle/child",
            parent=parent,
            parent_key="child",
            source_path="/tmp/bundle.memory",
            uuid="child-uuid",
        )
    )

    assert child is registry.get_asset("bundle/child")
    assert child is manager.get_runtime_asset_by_uuid("memory", "child-uuid")
    assert child.embedded_parent is parent
    assert child.embedded_parent_key == "child"
    assert child.source_path == Path("/tmp/bundle.memory")

    reloaded_parent = MemoryAsset(name="bundle-reloaded", uuid="bundle-reloaded-uuid")
    same_child = manager.get_or_create_embedded_asset(
        EmbeddedAssetSpec(
            type_id="memory",
            name="bundle/child-renamed",
            parent=reloaded_parent,
            parent_key="child-renamed",
            source_path="/tmp/bundle.memory",
            uuid="child-uuid",
        )
    )

    assert same_child is child
    assert child.embedded_parent is reloaded_parent
    assert child.embedded_parent_key == "child-renamed"


def test_runtime_manager_can_list_and_find_runtime_asset_names() -> None:
    manager = AssetRuntimeManager()

    def data_to_asset(data: str) -> MemoryAsset | None:
        for asset in registry.assets.values():
            if asset.cached_data == data:
                return asset
        return None

    registry = AssetRegistry(
        asset_class=MemoryAsset,
        uuid_registry=manager._assets_by_uuid,
        data_from_asset=lambda asset: asset.data,
        data_to_asset=data_to_asset,
    )
    manager.register_runtime_asset_registry("memory", registry)

    first = MemoryAsset(data="alpha-data", name="alpha", uuid="alpha-uuid")
    second = MemoryAsset(data="beta-data", name="beta", uuid="beta-uuid")
    manager.register_runtime_asset("memory", "alpha", first, uuid=first.uuid)
    manager.register_runtime_asset("memory", "beta", second, uuid=second.uuid)

    assert manager.list_runtime_asset_names("memory") == ["alpha", "beta"]
    assert manager.find_runtime_asset_name("memory", "beta-data") == "beta"
    assert manager.find_runtime_asset_name("memory", "missing") is None


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


def test_resource_manager_factory_is_publicly_readable() -> None:
    class FakeResourceManager:
        pass

    manager = FakeResourceManager()

    from termin_assets import set_resource_manager_factory

    set_resource_manager_factory(lambda: manager)
    try:
        assert get_resource_manager() is manager
    finally:
        set_resource_manager_factory(None)

    assert get_resource_manager() is None


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


def test_asset_runtime_manager_dispatches_runtime_plugins() -> None:
    manager = AssetRuntimeManager()
    registry = AssetRegistry(
        asset_class=Asset,
        uuid_registry=manager._assets_by_uuid,
        data_from_asset=lambda asset: asset,
    )
    manager.register_runtime_asset_registry("dummy", registry)

    class RuntimePlugin:
        type_id = "dummy"

        def register(self, context, result: PreLoadResult) -> None:
            asset = Asset(name=context.name, uuid=result.uuid)
            context.resource_manager.register_runtime_asset(
                self.type_id,
                context.name,
                asset,
                source_path=result.path,
                uuid=result.uuid,
            )

        def reload(self, context, result: PreLoadResult) -> None:
            asset = context.resource_manager.get_runtime_asset(self.type_id, context.name)
            if asset is not None:
                asset.source_path = result.path

    manager.asset_type_plugins.register_runtime(RuntimePlugin())

    result = PreLoadResult(resource_type="dummy", path="/tmp/probe.dummy", uuid="dummy-uuid")
    manager.register_file(result)

    asset = manager.get_runtime_asset("dummy", "probe")
    assert asset is not None
    assert manager.get_runtime_asset_by_uuid("dummy", "dummy-uuid") is asset
    assert manager.get_asset_by_uuid("dummy-uuid") is asset

    reloaded = PreLoadResult(resource_type="dummy", path="/var/tmp/probe.dummy", uuid="dummy-uuid")
    manager.reload_file(reloaded)

    assert asset.source_path == Path("/var/tmp/probe.dummy")


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
