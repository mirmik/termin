from termin_assets import (
    AssetTypeRegistry,
    PreLoadResult,
    get_uuid_from_spec,
    read_spec_file,
    write_spec_file,
)


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
