"""Prefab asset plugins."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tcbase import log

if TYPE_CHECKING:
    from termin_assets import AssetContext, AssetTypeRegistry, PreLoadResult


class PrefabImportPlugin:
    """Import-side plugin for prefab files."""

    type_id = "prefab"
    extensions = {".prefab"}
    priority = 30

    def preload(self, path: str) -> "PreLoadResult | None":
        from termin_assets import PreLoadResult

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            uuid = None
            try:
                data = json.loads(content)
                uuid = data.get("uuid")
            except json.JSONDecodeError:
                log.debug(f"[PrefabImportPlugin] Failed to parse JSON for UUID extraction: {path}")

            return PreLoadResult(
                resource_type=self.type_id,
                path=path,
                content=content,
                uuid=uuid,
            )

        except Exception:
            log.error(f"[PrefabImportPlugin] Failed to read {path}", exc_info=True)
            return None


class PrefabRuntimePlugin:
    """Runtime-side plugin for prefab registration and reload."""

    type_id = "prefab"

    def register(self, context: "AssetContext", result: "PreLoadResult") -> None:
        from termin.default_assets.prefab.asset import PrefabAsset

        rm = context.resource_manager
        name = context.name
        if rm.get_prefab_asset(name) is not None:
            return

        asset = None
        if result.uuid:
            candidate = rm.get_prefab_by_uuid(result.uuid)
            if isinstance(candidate, PrefabAsset):
                asset = candidate

        if asset is None:
            asset = PrefabAsset(
                data=None,
                name=name,
                source_path=result.path,
                uuid=result.uuid,
            )

        rm.register_prefab(name, asset, source_path=result.path)

    def reload(self, context: "AssetContext", result: "PreLoadResult") -> None:
        from termin.default_assets.prefab.asset import PrefabAsset

        rm = context.resource_manager
        name = context.name
        asset = rm.get_prefab_asset(name)
        if asset is None:
            return

        if not asset.is_loaded:
            return

        if not asset.should_reload_from_file():
            return

        new_asset = PrefabAsset.from_file(result.path, name=name)
        asset.update_from(new_asset)


class PrefabAssetPlugin(PrefabImportPlugin, PrefabRuntimePlugin):
    """Compatibility combined prefab plugin."""


def create_import_plugin() -> PrefabImportPlugin:
    return PrefabImportPlugin()


def create_runtime_plugin() -> PrefabRuntimePlugin:
    return PrefabRuntimePlugin()


def register_prefab_import_plugin(registry: "AssetTypeRegistry") -> None:
    registry.register_import(PrefabImportPlugin())


def register_prefab_runtime_plugin(registry: "AssetTypeRegistry") -> None:
    registry.register_runtime(PrefabRuntimePlugin())


def register_prefab_asset_plugin(registry: "AssetTypeRegistry") -> None:
    register_prefab_import_plugin(registry)
    register_prefab_runtime_plugin(registry)
