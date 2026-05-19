"""Render pipeline asset plugins."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from termin_assets import AssetContext, AssetTypeRegistry, PreLoadResult


class PipelineImportPlugin:
    """Import-side plugin for render pipeline files."""

    type_id = "pipeline"
    extensions = {".pipeline"}
    priority = 5

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


class PipelineRuntimePlugin:
    """Runtime-side plugin for render pipeline registration and reload."""

    type_id = "pipeline"

    def register(self, context: "AssetContext", result: "PreLoadResult") -> None:
        from termin.assets.pipeline_asset import PipelineAsset

        rm = context.resource_manager
        name = context.name
        uuid = result.spec_data.get("uuid") if result.spec_data else None
        if uuid and uuid in rm._assets_by_uuid:
            asset = rm._assets_by_uuid[uuid]
            if isinstance(asset, PipelineAsset):
                rm._pipeline_registry.assets[name] = asset
                asset.parse_spec(result.spec_data)
                return

        asset = rm._pipeline_registry.get_or_create_asset(
            name=name,
            source_path=result.path,
            uuid=uuid,
        )
        asset.parse_spec(result.spec_data)

    def reload(self, context: "AssetContext", result: "PreLoadResult") -> None:
        rm = context.resource_manager
        asset = rm._pipeline_registry.get_asset(context.name)
        if asset is None:
            return

        if not asset.is_loaded:
            return

        if not asset.should_reload_from_file():
            return

        asset.parse_spec(result.spec_data)
        asset.reload()


class PipelineAssetPlugin(PipelineImportPlugin, PipelineRuntimePlugin):
    """Compatibility combined render pipeline plugin."""


def register_pipeline_import_plugin(registry: "AssetTypeRegistry") -> None:
    registry.register_import(PipelineImportPlugin())


def register_pipeline_runtime_plugin(registry: "AssetTypeRegistry") -> None:
    registry.register_runtime(PipelineRuntimePlugin())


def register_pipeline_asset_plugin(registry: "AssetTypeRegistry") -> None:
    register_pipeline_import_plugin(registry)
    register_pipeline_runtime_plugin(registry)
