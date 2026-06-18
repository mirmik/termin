from termin.default_assets.navmesh.asset import NavMeshAsset
from termin.default_assets.navmesh.asset_plugin import create_import_plugin, create_runtime_plugin
from termin.default_assets.navmesh.handle import NavMeshHandle
from termin.navmesh import NavMeshAsset as PackageNavMeshAsset
from termin.navmesh import NavMeshHandle as PackageNavMeshHandle
from termin.navmesh.asset import NavMeshAsset as LegacyDomainNavMeshAsset
from termin.navmesh.asset_plugin import create_import_plugin as legacy_create_import_plugin
from termin.navmesh.asset_plugin import create_runtime_plugin as legacy_create_runtime_plugin
from termin.navmesh.handle import NavMeshHandle as LegacyDomainNavMeshHandle
from termin.navmesh.navmesh_asset import NavMeshAsset as LegacyNavMeshAsset
from termin.assets.navmesh_asset import NavMeshAsset as AppLegacyNavMeshAsset
from termin.assets.navmesh_handle import NavMeshHandle as LegacyNavMeshHandle


def test_navmesh_asset_legacy_module_reexports_canonical_class() -> None:
    assert PackageNavMeshAsset is NavMeshAsset
    assert LegacyDomainNavMeshAsset is NavMeshAsset
    assert LegacyNavMeshAsset is NavMeshAsset
    assert AppLegacyNavMeshAsset is NavMeshAsset


def test_navmesh_handle_legacy_module_reexports_canonical_class() -> None:
    assert PackageNavMeshHandle is NavMeshHandle
    assert LegacyDomainNavMeshHandle is NavMeshHandle
    assert LegacyNavMeshHandle is NavMeshHandle


def test_navmesh_plugin_legacy_modules_reexport_factories() -> None:
    assert legacy_create_import_plugin is create_import_plugin
    assert legacy_create_runtime_plugin is create_runtime_plugin
    assert create_import_plugin().type_id == "navmesh"
    assert create_runtime_plugin().type_id == "navmesh"
