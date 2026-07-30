from pathlib import Path

from termin_assets import AssetContext, PreLoadResult
from termin.default_assets.ui.asset_plugin import create_import_plugin, create_runtime_plugin
from termin.default_assets.ui.document_asset import UiDocumentSourceAsset
from termin.gui_native import UiDocumentAsset


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


def _source(text: str = "Hello") -> str:
    return f"""uiscript: 2
root:
  type: termin.gui.IconButton
  name: root
  icon: "+"
  tooltip: "{text}"
"""


def test_ui_runtime_plugin_registers_native_document(tmp_path: Path) -> None:
    UiDocumentAsset.clear_registry_for_tests()
    resource_manager = FakeResourceManager()
    path = tmp_path / "main.uiscript"
    path.write_text(_source(), encoding="utf-8")
    result = PreLoadResult(
        resource_type="ui",
        path=str(path),
        uuid="ui-uuid",
        spec_data={"uuid": "ui-uuid"},
    )

    create_runtime_plugin().register(
        AssetContext(resource_manager=resource_manager, name="main", uuid="ui-uuid"),
        result,
    )

    asset = resource_manager.get_runtime_asset("ui", "main")
    assert isinstance(asset, UiDocumentSourceAsset)
    assert asset.uuid == "ui-uuid"
    assert asset.source_path == path
    assert asset.is_loaded
    assert asset.resource.valid
    assert asset.resource.source_identity == str(path)
    assert asset.resource.revision == 1


def test_ui_reload_is_transactional(tmp_path: Path) -> None:
    UiDocumentAsset.clear_registry_for_tests()
    resource_manager = FakeResourceManager()
    path = tmp_path / "main.uiscript"
    path.write_text(_source("before"), encoding="utf-8")
    result = PreLoadResult(
        resource_type="ui",
        path=str(path),
        uuid="ui-uuid",
        spec_data={"uuid": "ui-uuid"},
    )
    context = AssetContext(
        resource_manager=resource_manager,
        name="main",
        uuid="ui-uuid",
    )
    plugin = create_runtime_plugin()
    plugin.register(context, result)
    before = UiDocumentAsset.from_uuid("ui-uuid")
    before_json = before.compiled_json()

    path.write_text("uiscript: 999\n", encoding="utf-8")
    assert plugin.reload(context, result) is False
    preserved = UiDocumentAsset.from_uuid("ui-uuid")
    assert preserved.valid
    assert preserved.revision == 1
    assert preserved.compiled_json() == before_json

    path.write_text(_source("after"), encoding="utf-8")
    assert plugin.reload(context, result) is True
    reloaded = UiDocumentAsset.from_uuid("ui-uuid")
    assert reloaded.revision == 2
    assert reloaded.handle.index == before.handle.index
    assert reloaded.handle.generation == before.handle.generation


def test_ui_import_plugin_creates_native_v2_source(tmp_path: Path) -> None:
    result = create_import_plugin().create_asset(str(tmp_path), "HUD")

    path = Path(result.path)
    assert path == tmp_path / "Assets" / "UI" / "HUD.uiscript"
    assert "uiscript: 2" in path.read_text(encoding="utf-8")
    assert result.uuid
    assert path.with_name(path.name + ".meta").exists()


def test_ui_entry_point_factories() -> None:
    assert create_import_plugin().type_id == "ui"
    assert create_runtime_plugin().type_id == "ui"


def test_ui_plugin_factories_use_canonical_classes() -> None:
    from termin.default_assets.ui.asset_plugin import UIImportPlugin

    assert type(create_import_plugin()) is UIImportPlugin
