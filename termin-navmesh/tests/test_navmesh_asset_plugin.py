from termin_assets import AssetTypeRegistry
from termin.navmesh.asset import NavMeshAsset
from termin.navmesh.asset_plugin import (
    create_import_plugin,
    create_runtime_plugin,
    register_navmesh_import_plugin,
    register_navmesh_runtime_plugin,
)
from termin.navmesh.navmesh_asset import NavMeshAsset as LegacyNavMeshAsset
from termin.navmesh.types import NavMesh


def test_navmesh_asset_wraps_navmesh() -> None:
    navmesh = NavMesh(name="source_navmesh")

    asset = NavMeshAsset.from_navmesh(navmesh, source_path="/tmp/source.navmesh")

    assert asset.name == "source_navmesh"
    assert asset.navmesh is navmesh
    assert str(asset.source_path) == "/tmp/source.navmesh"


def test_navmesh_asset_legacy_module_reexports_canonical_class() -> None:
    assert LegacyNavMeshAsset is NavMeshAsset


def test_navmesh_plugins_register_with_asset_registry() -> None:
    registry = AssetTypeRegistry()

    register_navmesh_import_plugin(registry)
    register_navmesh_runtime_plugin(registry)

    assert registry.get_import("navmesh") is not None
    assert registry.get_runtime("navmesh") is not None
    assert registry.get_for_extension(".navmesh")[0].type_id == "navmesh"


def test_navmesh_entry_point_factories() -> None:
    assert create_import_plugin().type_id == "navmesh"
    assert create_runtime_plugin().type_id == "navmesh"
