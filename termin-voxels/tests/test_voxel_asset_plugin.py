from termin_assets import AssetTypeRegistry
from termin.voxels.asset import VoxelGridAsset
from termin.voxels.asset_plugin import (
    create_import_plugin,
    create_runtime_plugin,
    register_voxel_grid_import_plugin,
    register_voxel_grid_runtime_plugin,
)
from termin.voxels.grid import VoxelGrid


def test_voxel_grid_asset_wraps_grid() -> None:
    grid = VoxelGrid(name="source_grid")

    asset = VoxelGridAsset.from_grid(grid, source_path="/tmp/source.voxels")

    assert asset.name == "source_grid"
    assert asset.grid is grid
    assert str(asset.source_path) == "/tmp/source.voxels"


def test_voxel_grid_plugins_register_with_asset_registry() -> None:
    registry = AssetTypeRegistry()

    register_voxel_grid_import_plugin(registry)
    register_voxel_grid_runtime_plugin(registry)

    assert registry.get_import("voxel_grid") is not None
    assert registry.get_runtime("voxel_grid") is not None
    assert registry.get_for_extension(".voxels")[0].type_id == "voxel_grid"


def test_voxel_grid_entry_point_factories() -> None:
    assert create_import_plugin().type_id == "voxel_grid"
    assert create_runtime_plugin().type_id == "voxel_grid"
