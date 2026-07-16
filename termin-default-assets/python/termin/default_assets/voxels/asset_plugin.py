"""Voxel grid asset plugins."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from termin_assets import AssetContext, AssetTypeRegistry, PreLoadResult


class VoxelGridImportPlugin:
    """Import-side plugin for voxel grid files."""

    type_id = "voxel_grid"
    extensions = {".voxels"}
    priority = 10

    def preload(self, path: str) -> "PreLoadResult | None":
        from termin_assets import PreLoadResult, read_spec_file

        spec_data = read_spec_file(path)
        uuid = spec_data.get("uuid") if spec_data else None
        return PreLoadResult(
            resource_type=self.type_id,
            path=path,
            content=None,
            uuid=uuid,
            spec_data=spec_data,
        )


class VoxelGridRuntimePlugin:
    """Runtime-side plugin for voxel grid registration and reload."""

    type_id = "voxel_grid"

    def register(self, context: "AssetContext", result: "PreLoadResult") -> None:
        from termin.default_assets.voxels.asset import VoxelGridAsset

        rm = context.resource_manager
        name = context.name
        if result.uuid is None and rm.get_runtime_asset(self.type_id, name) is not None:
            return

        asset = None
        if result.uuid:
            candidate = rm.get_runtime_asset_by_uuid(self.type_id, result.uuid)
            if isinstance(candidate, VoxelGridAsset):
                asset = candidate

        if asset is None:
            asset = VoxelGridAsset(
                grid=None,
                name=name,
                source_path=result.path,
                uuid=result.uuid,
            )

        asset.parse_spec(result.spec_data)
        rm.register_runtime_asset(self.type_id, name, asset, source_path=result.path, uuid=result.uuid)

    def reload(self, context: "AssetContext", result: "PreLoadResult") -> None:
        rm = context.resource_manager
        name = context.name
        asset = (
            rm.get_runtime_asset_by_uuid(self.type_id, result.uuid)
            if result.uuid
            else rm.get_runtime_asset(self.type_id, name)
        )
        if asset is None:
            return

        if not asset.is_loaded:
            return

        if not asset.should_reload_from_file():
            return

        asset.parse_spec(result.spec_data)
        asset.reload()

        if asset.grid is not None:
            from termin.voxels._voxels_native import TcVoxelGrid

            rm.voxel_grids[name] = TcVoxelGrid.from_uuid(asset.uuid)

    def unregister(self, context: "AssetContext", result: "PreLoadResult") -> None:
        context.resource_manager.unregister_runtime_asset(self.type_id, context.name, uuid=result.uuid)


class VoxelGridAssetPlugin(VoxelGridImportPlugin, VoxelGridRuntimePlugin):
    """Compatibility combined voxel grid plugin."""


def create_import_plugin() -> VoxelGridImportPlugin:
    return VoxelGridImportPlugin()


def create_runtime_plugin() -> VoxelGridRuntimePlugin:
    return VoxelGridRuntimePlugin()


def register_voxel_grid_import_plugin(registry: "AssetTypeRegistry") -> None:
    registry.register_import(VoxelGridImportPlugin())


def register_voxel_grid_runtime_plugin(registry: "AssetTypeRegistry") -> None:
    registry.register_runtime(VoxelGridRuntimePlugin())


def register_voxel_grid_asset_plugin(registry: "AssetTypeRegistry") -> None:
    register_voxel_grid_import_plugin(registry)
    register_voxel_grid_runtime_plugin(registry)
