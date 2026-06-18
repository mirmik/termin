"""Compatibility re-export for voxel grid asset plugins.

Canonical module: :mod:`termin.default_assets.voxels.asset_plugin`.
"""

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
    "VoxelGridAssetPlugin",
    "VoxelGridImportPlugin",
    "VoxelGridRuntimePlugin",
    "create_import_plugin",
    "create_runtime_plugin",
    "register_voxel_grid_asset_plugin",
    "register_voxel_grid_import_plugin",
    "register_voxel_grid_runtime_plugin",
]
