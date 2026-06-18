"""Default voxel asset adapters."""

from termin.default_assets.voxels.asset import VoxelGridAsset
from termin.default_assets.voxels.asset_plugin import (
    VoxelGridAssetPlugin,
    VoxelGridImportPlugin,
    VoxelGridRuntimePlugin,
    create_import_plugin,
    create_runtime_plugin,
    register_voxel_grid_asset_plugin,
    register_voxel_grid_import_plugin,
    register_voxel_grid_runtime_plugin,
)

__all__ = [
    "VoxelGridAsset",
    "VoxelGridAssetPlugin",
    "VoxelGridImportPlugin",
    "VoxelGridRuntimePlugin",
    "create_import_plugin",
    "create_runtime_plugin",
    "register_voxel_grid_asset_plugin",
    "register_voxel_grid_import_plugin",
    "register_voxel_grid_runtime_plugin",
]
