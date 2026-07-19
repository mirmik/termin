from pathlib import Path

from termin_assets import AssetContext, PreLoadResult, set_resource_manager_factory
from termin.default_assets.ui.asset import UIAsset
from termin.default_assets.ui.asset_plugin import create_import_plugin, create_runtime_plugin
from termin.default_assets.ui.handle import UIHandle


class FakeResourceManager:
    def __init__(self) -> None:
        self.by_name = {}
        self.by_uuid = {}

    def get_runtime_asset(self, type_id: str, name: str):
        return self.by_name.get((type_id, name))

    def get_runtime_asset_by_uuid(self, type_id: str, uuid: str):
        return self.by_uuid.get((type_id, uuid))

    def register_runtime_asset(self, type_id: str, name: str, asset, *, source_path=None, uuid=None) -> None:
        self.by_name[(type_id, name)] = asset
        if uuid is not None:
            self.by_uuid[(type_id, uuid)] = asset

    def get_ui_asset_by_uuid(self, uuid: str):
        return self.by_uuid.get(("ui", uuid))


def test_ui_runtime_plugin_registers_lazy_asset() -> None:
    resource_manager = FakeResourceManager()
    result = PreLoadResult(
        resource_type="ui",
        path="/tmp/main.uiscript",
        uuid="ui-uuid",
        spec_data={"uuid": "ui-uuid"},
    )

    create_runtime_plugin().register(
        AssetContext(resource_manager=resource_manager, name="main", uuid="ui-uuid"),
        result,
    )

    asset = resource_manager.get_runtime_asset("ui", "main")
    assert isinstance(asset, UIAsset)
    assert asset.uuid == "ui-uuid"
    assert asset.source_path == Path("/tmp/main.uiscript")
    assert not asset.is_loaded


def test_ui_handle_can_lookup_asset_by_uuid() -> None:
    resource_manager = FakeResourceManager()
    asset = UIAsset(name="main", uuid="ui-uuid")
    resource_manager.register_runtime_asset("ui", asset.name, asset, uuid=asset.uuid)

    set_resource_manager_factory(lambda: resource_manager)
    try:
        handle = UIHandle.from_uuid("ui-uuid")
        restored = UIHandle.deserialize({"type": "uuid", "uuid": "ui-uuid"})
    finally:
        set_resource_manager_factory(None)

    assert handle.asset is asset
    assert restored.asset is asset


def test_ui_entry_point_factories() -> None:
    assert create_import_plugin().type_id == "ui"
    assert create_runtime_plugin().type_id == "ui"


def test_ui_plugin_factories_use_canonical_classes() -> None:
    from termin.default_assets.ui.asset_plugin import UIImportPlugin

    assert type(create_import_plugin()) is UIImportPlugin
