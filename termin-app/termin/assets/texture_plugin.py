"""Texture asset plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tcbase import log

if TYPE_CHECKING:
    from termin_assets import AssetContext, AssetTypeRegistry, PreLoadResult


class TextureAssetPlugin:
    """Plugin handling lazy texture registration and reload."""

    type_id = "texture"
    extensions = {".png", ".jpg", ".jpeg", ".tga", ".bmp"}
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
        from termin.assets.texture_asset import TextureAsset
        from termin.texture import tc_texture_declare, tc_texture_set_load_callback

        rm = context.resource_manager
        name = context.name
        if name in rm._texture_assets:
            return

        asset = None
        if result.uuid:
            candidate = rm._assets_by_uuid.get(result.uuid)
            if isinstance(candidate, TextureAsset):
                asset = candidate

        if asset is None:
            asset = TextureAsset(
                texture_data=None,
                name=name,
                source_path=result.path,
                uuid=result.uuid,
            )

        asset.parse_spec(result.spec_data)
        rm._texture_registry.register(name, asset, source_path=result.path, uuid=result.uuid)

        texture = tc_texture_declare(asset.uuid, name)

        def load_texture(_texture) -> bool:
            if asset.ensure_loaded():
                return True
            log.error(f"[TextureAssetPlugin] Failed to lazy-load texture: {name} ({asset.uuid})")
            return False

        tc_texture_set_load_callback(texture, load_texture)

    def reload(self, context: "AssetContext", result: "PreLoadResult") -> None:
        rm = context.resource_manager
        asset = rm._texture_assets.get(context.name)
        if asset is None:
            return

        if not asset.is_loaded:
            return

        if not asset.should_reload_from_file():
            return

        asset.parse_spec(result.spec_data)
        asset.reload()
        asset.delete_gpu()


def register_texture_asset_plugin(registry: "AssetTypeRegistry") -> None:
    registry.register(TextureAssetPlugin())
