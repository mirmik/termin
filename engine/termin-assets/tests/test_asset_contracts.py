from pathlib import Path
import gc
import weakref

import pytest

from termin_assets import (
    Asset,
    AssetRecord,
    AssetRegistry,
    AssetStore,
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
from termin_assets import asset as asset_module
from tcbase import request_resource_load


def test_asset_core_classes_are_exported() -> None:
    assert Identifiable is not None
    assert Asset is not None
    assert DataAsset is not None
    assert EmbeddedAssetSpec is not None
    assert AssetRegistry is not None
    assert AssetStore is not None
    assert ResourceHandle is not None


class MemoryAsset(DataAsset[str]):
    def _parse_content(self, content: bytes | str) -> str | None:
        return str(content)


class RejectingAsset(DataAsset[str]):
    def _parse_content(self, content: bytes | str) -> str | None:
        return None


def test_data_asset_can_store_lazy_runtime_data_without_private_mutation() -> None:
    asset = MemoryAsset(name="probe")

    asset.set_runtime_data("declared-handle", loaded=False)

    assert asset.cached_data == "declared-handle"
    assert not asset.is_loaded

    asset.set_runtime_data("ready-data")

    assert asset.cached_data == "ready-data"
    assert asset.data == "ready-data"
    assert asset.is_loaded


def test_data_asset_reload_preserves_live_data_when_new_content_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "probe.memory"
    source.write_text("invalid", encoding="utf-8")
    asset = RejectingAsset(data="live-data", name="probe", source_path=source)

    assert not asset.reload()
    assert asset.cached_data == "live-data"
    assert asset.is_loaded
    assert asset.version == 0


def test_asset_runtime_load_logs_begin_and_end_with_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "probe.memory"
    source.write_text("payload", encoding="utf-8")
    messages: list[str] = []
    monkeypatch.setattr(asset_module.log, "info", messages.append)
    asset = MemoryAsset(
        name="probe",
        source_path=source,
        uuid="probe-uuid",
    )

    assert asset.ensure_loaded()

    assert messages[0].startswith(
        "[AssetRuntimeLoad] begin operation=load type=MemoryAsset "
        "name='probe' uuid='probe-uuid'"
    )
    assert f"path='{source}'" in messages[0]
    assert messages[1].startswith(
        "[AssetRuntimeLoad] end operation=load type=MemoryAsset "
        "name='probe' uuid='probe-uuid' status=ok duration_ms="
    )


def test_runtime_manager_get_or_create_embedded_asset_uses_runtime_registry() -> None:
    manager = AssetRuntimeManager()
    registry = AssetRegistry(
        asset_class=MemoryAsset,
        asset_store=manager._asset_store,
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
        asset_store=manager._asset_store,
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


def test_asset_registry_rejects_uuid_collisions_without_corrupting_existing_mapping() -> None:
    manager = AssetRuntimeManager()
    registry = AssetRegistry(
        asset_class=MemoryAsset,
        asset_store=manager._asset_store,
        data_from_asset=lambda asset: asset.data,
    )
    first = MemoryAsset(data="first", name="first", uuid="shared-uuid")
    second = MemoryAsset(data="second", name="second", uuid="shared-uuid")

    registry.register("first", first)
    with pytest.raises(ValueError, match="already registered"):
        registry.register("second", second)

    assert registry.get_asset("first") is first
    assert registry.get_asset("second") is None
    assert manager.get_asset_by_uuid("shared-uuid") is first


def test_asset_registry_allows_duplicate_names_with_uuid_canonical_identity() -> None:
    manager = AssetRuntimeManager()
    registry = AssetRegistry(
        asset_class=MemoryAsset,
        asset_store=manager._asset_store,
        data_from_asset=lambda asset: asset.data,
    )
    manager.register_runtime_asset_registry("memory", registry)
    first = MemoryAsset(data="first", name="shared", uuid="first-uuid")
    second = MemoryAsset(data="second", name="shared", uuid="second-uuid")

    registry.register("shared", first)
    registry.register("shared", second)

    assert registry.find_assets_by_name("shared") == (first, second)
    assert manager.find_runtime_assets_by_name("memory", "shared") == (first, second)
    assert registry.get_asset("shared") is None
    assert registry.get_asset_by_uuid("first-uuid") is first
    assert registry.get_asset_by_uuid("second-uuid") is second
    assert manager.get_asset_by_uuid("first-uuid") is first
    assert manager.get_asset_by_uuid("second-uuid") is second


def test_asset_registry_rename_unregister_and_clear_keep_indexes_consistent() -> None:
    manager = AssetRuntimeManager()
    registry = AssetRegistry(
        asset_class=MemoryAsset,
        asset_store=manager._asset_store,
        data_from_asset=lambda asset: asset.data,
    )
    first = MemoryAsset(data="first", name="shared", uuid="first-uuid")
    second = MemoryAsset(data="second", name="shared", uuid="second-uuid")
    registry.register("shared", first)
    registry.register("shared", second)

    assert registry.rename(first.uuid, "renamed")
    assert first.name == "renamed"
    assert registry.find_assets_by_name("shared") == (second,)
    assert registry.find_assets_by_name("renamed") == (first,)
    assert registry.get_asset("shared") is second

    with pytest.raises(AttributeError, match="AssetRegistry.rename"):
        first.name = "bypassed"

    assert registry.unregister_by_uuid(second.uuid) is second
    assert manager.get_asset_by_uuid(second.uuid) is None
    assert registry.find_assets_by_name("shared") == ()

    registry.clear()
    assert len(registry) == 0
    assert len(manager.assets_by_uuid) == 0
    assert registry.find_assets_by_name("renamed") == ()


def test_asset_registry_views_are_read_only_and_reload_preserves_identity(
    tmp_path: Path,
) -> None:
    manager = AssetRuntimeManager()
    registry = AssetRegistry(
        asset_class=MemoryAsset,
        asset_store=manager._asset_store,
        data_from_asset=lambda asset: asset.data,
    )
    source = tmp_path / "probe.memory"
    source.write_text("first", encoding="utf-8")
    asset = MemoryAsset(name="probe", source_path=source, uuid="probe-uuid")
    registry.register("probe", asset)

    with pytest.raises(TypeError):
        registry.assets["other"] = asset
    with pytest.raises(TypeError):
        manager.assets_by_uuid["other"] = asset

    assert asset.ensure_loaded()
    source.write_text("second", encoding="utf-8")
    assert asset.reload()
    assert asset.version == 1
    assert registry.get_asset_by_uuid(asset.uuid) is asset
    assert manager.get_asset_by_uuid(asset.uuid) is asset

    with pytest.raises(ValueError, match="UUID identity is immutable"):
        asset.parse_spec({"uuid": "replacement-uuid"})
    assert asset.uuid == "probe-uuid"
    assert manager.get_asset_by_uuid("probe-uuid") is asset
    assert manager.get_asset_by_uuid("replacement-uuid") is None


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


def test_process_resource_loader_uses_current_canonical_manager() -> None:
    first_asset = MemoryAsset(data="first", name="first", uuid="first-uuid")
    second_asset = MemoryAsset(data="second", name="second", uuid="second-uuid")

    class FakeResourceManager:
        def __init__(self, asset: Asset):
            self.asset = asset

        def get_asset_by_uuid(self, uuid: str) -> Asset | None:
            return self.asset if self.asset.uuid == uuid else None

    from termin_assets import set_resource_manager_factory

    first_manager = FakeResourceManager(first_asset)
    first_ref = weakref.ref(first_manager)
    set_resource_manager_factory(first_ref)
    assert request_resource_load("first-uuid")
    assert not request_resource_load("missing")

    second_manager = FakeResourceManager(second_asset)
    set_resource_manager_factory(lambda: second_manager)
    del first_manager
    gc.collect()

    try:
        assert first_ref() is None
        assert request_resource_load("second-uuid")
        assert not request_resource_load("first-uuid")
    finally:
        set_resource_manager_factory(None)

    assert not request_resource_load("second-uuid")


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
        asset_store=manager._asset_store,
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
            asset = context.resource_manager.get_runtime_asset_by_uuid(self.type_id, context.uuid)
            if asset is not None:
                asset.source_path = result.path

        def unregister(self, context, result: PreLoadResult) -> None:
            context.resource_manager.unregister_runtime_asset_by_uuid(self.type_id, context.uuid)

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

    manager.unregister_file(reloaded)

    assert manager.get_runtime_asset("dummy", "probe") is None
    assert manager.get_runtime_asset_by_uuid("dummy", "dummy-uuid") is None
    assert manager.get_asset_by_uuid("dummy-uuid") is None


def test_file_lifecycle_is_uuid_canonical_for_duplicate_names() -> None:
    manager = AssetRuntimeManager()
    registry = AssetRegistry(
        asset_class=Asset,
        asset_store=manager._asset_store,
        data_from_asset=lambda asset: asset,
    )
    manager.register_runtime_asset_registry("dummy", registry)

    class RuntimePlugin:
        type_id = "dummy"

        def register(self, context, result: PreLoadResult) -> None:
            asset = context.resource_manager.get_runtime_asset_by_uuid(self.type_id, context.uuid)
            if asset is None:
                asset = Asset(name=context.name, source_path=result.path, uuid=context.uuid)
            context.resource_manager.register_runtime_asset(
                self.type_id,
                context.name,
                asset,
                source_path=result.path,
                uuid=context.uuid,
            )

        def reload(self, context, result: PreLoadResult) -> None:
            asset = context.resource_manager.get_runtime_asset_by_uuid(self.type_id, context.uuid)
            assert asset is not None
            asset.source_path = result.path

        def unregister(self, context, result: PreLoadResult) -> None:
            context.resource_manager.unregister_runtime_asset_by_uuid(self.type_id, context.uuid)

    manager.asset_type_plugins.register_runtime(RuntimePlugin())
    first = PreLoadResult(resource_type="dummy", path="/one/shared.dummy", uuid="uuid-one")
    second = PreLoadResult(resource_type="dummy", path="/two/shared.dummy", uuid="uuid-two")

    first_registration = manager.register_file(first)
    second_registration = manager.register_file(second)
    assert first_registration is not None
    assert second_registration is not None
    first_asset = manager.get_runtime_asset_by_uuid("dummy", "uuid-one")
    second_asset = manager.get_runtime_asset_by_uuid("dummy", "uuid-two")
    assert first_asset is not None
    assert second_asset is not None
    assert first_asset is not second_asset

    first_reload = PreLoadResult(
        resource_type="dummy",
        path="/one/shared-reloaded.dummy",
        uuid="uuid-one",
    )
    assert manager.reload_file(first_reload, first_registration)
    assert manager.get_runtime_asset_by_uuid("dummy", "uuid-one") is first_asset
    assert first_asset.source_path == Path("/one/shared-reloaded.dummy")
    assert second_asset.source_path == Path("/two/shared.dummy")

    assert manager.unregister_file(first_reload, first_registration)
    assert manager.get_runtime_asset_by_uuid("dummy", "uuid-one") is None
    assert manager.get_runtime_asset_by_uuid("dummy", "uuid-two") is second_asset


def test_file_registration_rejects_missing_and_colliding_uuid() -> None:
    manager = AssetRuntimeManager()
    registry = AssetRegistry(
        asset_class=Asset,
        asset_store=manager._asset_store,
        data_from_asset=lambda asset: asset,
    )
    manager.register_runtime_asset_registry("dummy", registry)
    calls: list[str] = []

    class RuntimePlugin:
        type_id = "dummy"

        def register(self, context, result: PreLoadResult) -> None:
            calls.append(result.path)
            context.resource_manager.register_runtime_asset(
                self.type_id,
                context.name,
                Asset(name=context.name, source_path=result.path, uuid=context.uuid),
                source_path=result.path,
                uuid=context.uuid,
            )

        def reload(self, context, result: PreLoadResult) -> None:
            pass

    manager.asset_type_plugins.register_runtime(RuntimePlugin())

    missing = PreLoadResult(resource_type="dummy", path="/one/missing.dummy")
    assert manager.register_file(missing) is None
    assert calls == []

    first = PreLoadResult(resource_type="dummy", path="/one/probe.dummy", uuid="shared-uuid")
    collision = PreLoadResult(resource_type="dummy", path="/two/probe.dummy", uuid="shared-uuid")
    assert manager.register_file(first) is not None
    assert manager.register_file(collision) is None
    assert calls == ["/one/probe.dummy"]
    asset = manager.get_runtime_asset_by_uuid("dummy", "shared-uuid")
    assert asset is not None
    assert asset.source_path == Path("/one/probe.dummy")


def test_asset_reload_events_are_manager_local_versioned_and_unsubscribable() -> None:
    manager = AssetRuntimeManager()
    other_manager = AssetRuntimeManager()
    registry = AssetRegistry(
        asset_class=Asset,
        asset_store=manager._asset_store,
        data_from_asset=lambda asset: asset,
    )
    manager.register_runtime_asset_registry("dummy", registry)

    class VersionedRuntimePlugin:
        type_id = "dummy"

        def register(self, context, result: PreLoadResult) -> None:
            context.resource_manager.register_runtime_asset(
                self.type_id,
                context.name,
                Asset(name=context.name, uuid=result.uuid),
                source_path=result.path,
                uuid=result.uuid,
            )

        def reload(self, context, result: PreLoadResult) -> bool:
            asset = context.resource_manager.get_runtime_asset_by_uuid(self.type_id, result.uuid)
            assert asset is not None
            asset._bump_version()
            return True

    manager.asset_type_plugins.register_runtime(VersionedRuntimePlugin())
    events = []
    other_events = []
    subscription = manager.subscribe_asset_reloaded(events.append)
    other_manager.subscribe_asset_reloaded(other_events.append)

    result = PreLoadResult(resource_type="dummy", path="/tmp/probe.dummy", uuid="dummy-uuid")
    manager.register_file(result)
    assert manager.reload_file(result)

    assert [(event.type_id, event.name, event.uuid, event.version) for event in events] == [
        ("dummy", "probe", "dummy-uuid", 1)
    ]
    assert other_events == []

    subscription.close()
    assert manager.reload_file(result)
    assert len(events) == 1


def test_external_runtime_plugin_can_reload_without_generic_asset_registry() -> None:
    manager = AssetRuntimeManager()

    class ExternalRuntimePlugin:
        type_id = "external"

        def register(self, context, result: PreLoadResult) -> None:
            context.resource_manager.external_assets.upsert(
                AssetRecord(
                    type_id=self.type_id,
                    name=context.name,
                    path=result.path,
                    uuid=result.uuid,
                )
            )

        def reload(self, context, result: PreLoadResult) -> None:
            self.register(context, result)

    manager.asset_type_plugins.register_runtime(ExternalRuntimePlugin())
    result = PreLoadResult(
        resource_type="external",
        path="/tmp/probe.external",
        uuid="external-uuid",
    )

    manager.register_file(result)
    assert manager.reload_file(result)

    record = manager.external_assets.get_by_uuid("external", "external-uuid")
    assert record is not None
    assert record.path == "/tmp/probe.external"


def test_spec_file_helpers_use_meta_only_and_leave_unrelated_spec_files(tmp_path) -> None:
    asset_path = tmp_path / "probe.obj"
    asset_path.write_text("", encoding="utf-8")
    spec_path = tmp_path / "probe.obj.spec"
    spec_path.write_text('{"uuid": "legacy"}', encoding="utf-8")

    assert read_spec_file(str(asset_path)) is None
    assert get_uuid_from_spec(str(asset_path)) is None

    assert write_spec_file(str(asset_path), {"uuid": "meta"})
    assert read_spec_file(str(asset_path)) == {"uuid": "meta"}
    assert spec_path.exists()


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
