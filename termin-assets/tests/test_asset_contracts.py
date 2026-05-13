from termin_assets import AssetTypeRegistry, PreLoadResult


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
