from termin.default_assets.voxels.asset import VoxelGridAsset
from termin.default_assets.voxels.asset_plugin import create_import_plugin, create_runtime_plugin
from termin.voxels.asset import VoxelGridAsset as LegacyDomainVoxelGridAsset
from termin.voxels.asset_plugin import create_import_plugin as legacy_create_import_plugin
from termin.voxels.asset_plugin import create_runtime_plugin as legacy_create_runtime_plugin


def test_voxel_grid_domain_legacy_modules_reexport_canonical_class() -> None:
    assert LegacyDomainVoxelGridAsset is VoxelGridAsset


def test_voxel_grid_plugin_legacy_modules_reexport_factories() -> None:
    assert legacy_create_import_plugin is create_import_plugin
    assert legacy_create_runtime_plugin is create_runtime_plugin
    assert create_import_plugin().type_id == "voxel_grid"
    assert create_runtime_plugin().type_id == "voxel_grid"
