"""GLSL include asset plugins."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from termin_assets import AssetContext, AssetTypeRegistry, PreLoadResult


class GlslImportPlugin:
    """Import-side plugin for GLSL include files."""

    type_id = "glsl"
    extensions = {".glsl"}
    priority = -10

    def preload(self, path: str) -> "PreLoadResult | None":
        from termin_assets import AssetIdentityPolicy, PreLoadResult, read_spec_file

        spec_data = read_spec_file(path)
        uuid = spec_data.get("uuid") if spec_data else None
        return PreLoadResult(
            resource_type=self.type_id,
            path=path,
            content=None,
            uuid=uuid,
            spec_data=spec_data,
            identity_policy=AssetIdentityPolicy.GENERATE_SIDECAR,
        )


class GlslRuntimePlugin:
    """Runtime-side plugin for GLSL include registration and reload."""

    type_id = "glsl"

    def register(self, context: "AssetContext", result: "PreLoadResult") -> None:
        from termin.default_assets.render.glsl_asset import GlslAsset

        rm = context.resource_manager
        name = context.name
        uuid = context.uuid
        asset = rm.get_runtime_asset_by_uuid(self.type_id, uuid)
        if isinstance(asset, GlslAsset):
            rm.register_runtime_asset(self.type_id, name, asset, source_path=result.path, uuid=uuid)
            asset.parse_spec(result.spec_data)
            return

        asset = rm.get_or_create_runtime_asset(
            self.type_id,
            name=name,
            source_path=result.path,
            uuid=uuid,
        )
        asset.parse_spec(result.spec_data)

    def reload(self, context: "AssetContext", result: "PreLoadResult") -> None:
        rm = context.resource_manager
        asset = rm.get_runtime_asset_by_uuid(self.type_id, context.uuid)
        if asset is None:
            return

        if not asset.should_reload_from_file():
            return

        asset.parse_spec(result.spec_data)
        if not asset.is_loaded:
            asset.ensure_loaded()
        else:
            asset.reload()

    def unregister(self, context: "AssetContext", result: "PreLoadResult") -> None:
        context.resource_manager.unregister_runtime_asset_by_uuid(self.type_id, context.uuid)


class GlslAssetPlugin(GlslImportPlugin, GlslRuntimePlugin):
    """Compatibility combined GLSL plugin."""


def create_import_plugin() -> GlslImportPlugin:
    return GlslImportPlugin()


def create_runtime_plugin() -> GlslRuntimePlugin:
    return GlslRuntimePlugin()


def register_glsl_import_plugin(registry: "AssetTypeRegistry") -> None:
    registry.register_import(GlslImportPlugin())


def register_glsl_runtime_plugin(registry: "AssetTypeRegistry") -> None:
    registry.register_runtime(GlslRuntimePlugin())


def register_glsl_asset_plugin(registry: "AssetTypeRegistry") -> None:
    register_glsl_import_plugin(registry)
    register_glsl_runtime_plugin(registry)
