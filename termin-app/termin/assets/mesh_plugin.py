"""Mesh asset plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from termin_assets import AssetContext, AssetTypeRegistry, PreLoadResult


class MeshAssetPlugin:
    """Plugin handling standalone mesh asset registration and reload."""

    type_id = "mesh"
    extensions = {".stl", ".obj"}
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

    def register(self, context: "AssetContext", result: "PreLoadResult") -> None:
        from termin.assets.mesh_asset import MeshAsset

        rm = context.resource_manager
        name = context.name
        if name in rm._mesh_assets:
            return

        asset = None
        if result.uuid:
            candidate = rm._assets_by_uuid.get(result.uuid)
            if isinstance(candidate, MeshAsset):
                asset = candidate

        if asset is None:
            asset = MeshAsset(
                mesh_data=None,
                name=name,
                source_path=result.path,
                uuid=result.uuid,
            )

        asset.parse_spec(result.spec_data)
        rm._mesh_registry.register(name, asset, source_path=result.path, uuid=result.uuid)

    def reload(self, context: "AssetContext", result: "PreLoadResult") -> None:
        rm = context.resource_manager
        asset = rm._mesh_assets.get(context.name)
        if asset is None:
            return

        if not asset.is_loaded:
            return

        if not asset.should_reload_from_file():
            return

        asset.parse_spec(result.spec_data)
        asset.reload()
        asset.delete_gpu()


def register_mesh_asset_plugin(registry: "AssetTypeRegistry") -> None:
    registry.register(MeshAssetPlugin())
