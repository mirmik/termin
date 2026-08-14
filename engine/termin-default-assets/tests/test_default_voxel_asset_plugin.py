from pathlib import Path

from termin_assets import AssetTypeRegistry
from termin.default_assets.voxels.asset import VoxelGridAsset
from termin.default_assets.voxels.asset_plugin import (
    create_import_plugin,
    create_runtime_plugin,
    register_voxel_grid_import_plugin,
    register_voxel_grid_runtime_plugin,
)
from termin.voxels._voxels_native import TcVoxelGrid, VoxelGridHandle
from termin.voxels.grid import VoxelGrid


def test_voxel_grid_asset_wraps_grid() -> None:
    grid = VoxelGrid(name="source_grid")

    asset = VoxelGridAsset.from_grid(grid, source_path="/tmp/source.voxels")

    assert asset.name == "source_grid"
    assert asset.grid is grid
    assert asset.source_path == Path("/tmp/source.voxels")
    assert TcVoxelGrid.from_name("source_grid").uuid == asset.uuid


def test_voxel_grid_asset_declares_core_runtime_resource() -> None:
    grid = VoxelGrid(name="declared_grid")

    asset = VoxelGridAsset.from_grid(grid, source_path="/tmp/declared.voxels")
    by_uuid = TcVoxelGrid.from_uuid(asset.uuid)
    by_name = TcVoxelGrid.from_name("declared_grid")

    assert VoxelGridHandle is TcVoxelGrid
    assert by_uuid.is_valid
    assert by_name.is_valid
    assert by_uuid.uuid == asset.uuid
    assert by_name.uuid == asset.uuid
    assert by_uuid.grid.get(0, 0, 0) == grid.get(0, 0, 0)


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
