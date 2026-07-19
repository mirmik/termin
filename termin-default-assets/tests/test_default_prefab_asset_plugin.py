import json
from pathlib import Path

from termin.prefab.asset import PrefabAsset
from termin.prefab.asset_plugin import create_import_plugin, create_runtime_plugin
from termin_assets import AssetContext, PreLoadResult


class FakeResourceManager:
    def __init__(self) -> None:
        self.prefabs = {}
        self.by_uuid = {}

    def get_prefab_asset(self, name: str):
        return self.prefabs.get(name)

    def get_prefab_by_uuid(self, uuid: str):
        return self.by_uuid.get(uuid)

    def register_prefab(self, name: str, asset, source_path: str | None = None) -> None:
        self.prefabs[name] = asset
        self.by_uuid[asset.uuid] = asset
        if source_path is not None:
            asset.source_path = source_path


def _empty_entity_data(uuid: str, name: str) -> dict[str, object]:
    return {
        "uuid": uuid,
        "name": name,
        "priority": 0,
        "visible": True,
        "enabled": True,
        "pickable": True,
        "selectable": True,
        "layer": 0,
        "flags": 0,
        "pose": {
            "position": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0, 1.0],
        },
        "scale": [1.0, 1.0, 1.0],
        "components": [],
        "children": [],
    }


def test_prefab_runtime_plugin_registers_lazy_asset() -> None:
    resource_manager = FakeResourceManager()
    result = PreLoadResult(
        resource_type="prefab",
        path="/tmp/Enemy.prefab",
        uuid="prefab-uuid",
    )

    create_runtime_plugin().register(
        AssetContext(resource_manager=resource_manager, name="Enemy", uuid="prefab-uuid"),
        result,
    )

    asset = resource_manager.get_prefab_asset("Enemy")
    assert isinstance(asset, PrefabAsset)
    assert asset.uuid == "prefab-uuid"
    assert asset.source_path == Path("/tmp/Enemy.prefab")
    assert not asset.is_loaded


def test_prefab_import_plugin_extracts_uuid(tmp_path: Path) -> None:
    prefab_path = tmp_path / "Enemy.prefab"
    prefab_path.write_text(
        '{"version": "3.0", "uuid": "prefab-uuid", "root": {"uuid": "enemy-root", "name": "Enemy", "components": [], "children": []}}',
        encoding="utf-8",
    )

    result = create_import_plugin().preload(str(prefab_path))

    assert result is not None
    assert result.resource_type == "prefab"
    assert result.uuid == "prefab-uuid"
    assert result.content is not None


def test_prefab_asset_file_helpers(tmp_path: Path) -> None:
    prefab_path = tmp_path / "Enemy.prefab"
    root_data = _empty_entity_data("enemy-root", "Enemy")
    prefab_path.write_text(
        json.dumps({"version": "3.0", "uuid": "prefab-uuid", "root": root_data}),
        encoding="utf-8",
    )

    asset = PrefabAsset.from_file(prefab_path)

    assert asset.name == "Enemy"
    assert asset.uuid == "prefab-uuid"
    assert asset.root_data == root_data
    assert asset.get_entity_count() == 1


def test_prefab_entry_point_factories() -> None:
    assert create_import_plugin().type_id == "prefab"
    assert create_runtime_plugin().type_id == "prefab"


def test_prefab_plugin_factories_use_canonical_classes() -> None:
    from termin.prefab.asset_plugin import PrefabImportPlugin

    assert type(create_import_plugin()) is PrefabImportPlugin
