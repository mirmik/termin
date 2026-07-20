"""Render pipeline asset plugins."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tcbase import log

if TYPE_CHECKING:
    from termin_assets import AssetContext, AssetTypeRegistry, PreLoadResult


class PipelineImportPlugin:
    """Import-side plugin for render pipeline files."""

    type_id = "pipeline"
    extensions = {".pipeline"}
    priority = 5

    def preload(self, path: str) -> "PreLoadResult | None":
        from termin_assets import PreLoadResult, read_spec_file

        try:
            with open(path, "r", encoding="utf-8") as source_file:
                content = source_file.read()
            data = json.loads(content)
        except (OSError, json.JSONDecodeError) as exc:
            log.error(f"[PipelineImportPlugin] Failed to parse {path}: {exc}")
            return None

        if not isinstance(data, dict):
            log.error(f"[PipelineImportPlugin] Pipeline document must be a JSON object: {path}")
            return None

        spec_data = read_spec_file(path)
        spec_uuid = spec_data.get("uuid") if spec_data else None
        embedded_uuid = data.get("uuid")
        if spec_uuid is not None and not isinstance(spec_uuid, str):
            log.error(f"[PipelineImportPlugin] Invalid UUID in sidecar metadata: {path}")
            return None
        if embedded_uuid is not None and (not isinstance(embedded_uuid, str) or not embedded_uuid):
            log.error(f"[PipelineImportPlugin] Invalid embedded UUID: {path}")
            return None
        if spec_uuid and embedded_uuid and spec_uuid != embedded_uuid:
            log.error(f"[PipelineImportPlugin] UUID mismatch between pipeline and sidecar metadata: {path}")
            return None
        if not embedded_uuid and not spec_uuid:
            log.error(f"[PipelineImportPlugin] Pipeline has no persistent UUID: {path}")
            return None

        return PreLoadResult(
            resource_type=self.type_id,
            path=path,
            content=None,
            uuid=embedded_uuid or spec_uuid,
            spec_data=spec_data,
        )


class PipelineRuntimePlugin:
    """Runtime-side plugin for render pipeline registration and reload."""

    type_id = "pipeline"

    def register(self, context: "AssetContext", result: "PreLoadResult") -> None:
        from termin.default_assets.render.pipeline_asset import PipelineAsset

        rm = context.resource_manager
        name = context.name
        uuid = context.uuid
        asset = rm.get_runtime_asset_by_uuid(self.type_id, uuid)
        if isinstance(asset, PipelineAsset):
            asset.bind_resource_manager(rm)
            rm.register_runtime_asset(self.type_id, name, asset, source_path=result.path, uuid=uuid)
            return

        asset = rm.get_or_create_runtime_asset(
            self.type_id,
            name=name,
            source_path=result.path,
            uuid=uuid,
        )
        asset.bind_resource_manager(rm)

    def reload(self, context: "AssetContext", result: "PreLoadResult") -> bool:
        rm = context.resource_manager
        asset = rm.get_runtime_asset_by_uuid(self.type_id, context.uuid)
        if asset is None:
            log.error(f"[PipelineRuntimePlugin] Pipeline asset is not registered: {context.name}")
            return False

        if not asset.is_loaded:
            return True

        if not asset.should_reload_from_file():
            return True

        return asset.reload()

    def unregister(self, context: "AssetContext", result: "PreLoadResult") -> None:
        context.resource_manager.unregister_runtime_asset_by_uuid(self.type_id, context.uuid)


class PipelineAssetPlugin(PipelineImportPlugin, PipelineRuntimePlugin):
    """Compatibility combined render pipeline plugin."""


def create_import_plugin() -> PipelineImportPlugin:
    return PipelineImportPlugin()


def create_runtime_plugin() -> PipelineRuntimePlugin:
    return PipelineRuntimePlugin()


def register_pipeline_import_plugin(registry: "AssetTypeRegistry") -> None:
    registry.register_import(PipelineImportPlugin())


def register_pipeline_runtime_plugin(registry: "AssetTypeRegistry") -> None:
    registry.register_runtime(PipelineRuntimePlugin())


def register_pipeline_asset_plugin(registry: "AssetTypeRegistry") -> None:
    register_pipeline_import_plugin(registry)
    register_pipeline_runtime_plugin(registry)
