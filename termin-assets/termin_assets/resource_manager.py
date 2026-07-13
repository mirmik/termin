"""Core asset runtime manager."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from tcbase import log

from termin_assets.asset import Asset
from termin_assets.catalog import AssetCatalog
from termin_assets.default_plugins import register_default_asset_plugins
from termin_assets.embedded_asset import EmbeddedAssetSpec
from termin_assets.plugin import AssetContext, AssetRuntimeUnregisterPlugin, AssetTypeRegistry

if TYPE_CHECKING:
    from termin_assets.asset_registry import AssetRegistry
    from termin_assets.preload import PreLoadResult


class AssetRuntimeManager:
    """Core asset runtime state and plugin dispatch.

    Domain-specific typed registries are registered by application/domain
    subclasses; this class owns only the shared plugin, UUID and external asset
    catalog mechanics.
    """

    _instance: "AssetRuntimeManager | None" = None

    def __init__(self) -> None:
        self._assets_by_uuid: dict[str, Asset] = {}
        self._asset_type_plugins = AssetTypeRegistry()
        self.external_assets = AssetCatalog()
        self._runtime_asset_registries: dict[str, "AssetRegistry"] = {}

    @property
    def asset_type_plugins(self) -> AssetTypeRegistry:
        return self._asset_type_plugins

    def register_default_asset_type_plugins(self) -> None:
        """Register installed asset type plugins into this manager."""
        register_default_asset_plugins(self._asset_type_plugins)

    def register_runtime_asset_registry(self, type_id: str, registry: "AssetRegistry") -> None:
        """Attach a typed runtime asset registry for plugin dispatch."""
        self._runtime_asset_registries[type_id] = registry

    def get_runtime_asset(self, type_id: str, name: str):
        """Get a registered runtime asset by plugin type id and name."""
        registry = self._runtime_asset_registries.get(type_id)
        if registry is None:
            log.error(f"[AssetRuntimeManager] Runtime asset registry is not registered: {type_id}")
            return None
        return registry.get_asset(name)

    def get_runtime_asset_by_uuid(self, type_id: str, uuid: str):
        """Get a registered runtime asset by plugin type id and UUID."""
        registry = self._runtime_asset_registries.get(type_id)
        if registry is None:
            log.error(f"[AssetRuntimeManager] Runtime asset registry is not registered: {type_id}")
            return None
        return registry.get_asset_by_uuid(uuid)

    def list_runtime_asset_names(self, type_id: str) -> list[str]:
        """List registered runtime asset names by plugin type id."""
        registry = self._runtime_asset_registries.get(type_id)
        if registry is None:
            log.error(f"[AssetRuntimeManager] Runtime asset registry is not registered: {type_id}")
            return []
        return registry.list_names()

    def find_runtime_asset_name(self, type_id: str, data) -> str | None:
        """Find a registered runtime asset name by plugin type id and data value."""
        registry = self._runtime_asset_registries.get(type_id)
        if registry is None:
            log.error(f"[AssetRuntimeManager] Runtime asset registry is not registered: {type_id}")
            return None
        return registry.find_name(data)

    def register_runtime_asset(
        self,
        type_id: str,
        name: str,
        asset: Asset,
        source_path: str | None = None,
        uuid: str | None = None,
    ) -> None:
        """Register a runtime asset through its plugin type registry."""
        registry = self._runtime_asset_registries.get(type_id)
        if registry is None:
            log.error(f"[AssetRuntimeManager] Runtime asset registry is not registered: {type_id}")
            raise KeyError(type_id)
        registry.register(name, asset, source_path, uuid)

    def unregister_runtime_asset(self, type_id: str, name: str) -> None:
        """Remove a runtime asset through its plugin type registry."""
        registry = self._runtime_asset_registries.get(type_id)
        if registry is None:
            log.error(f"[AssetRuntimeManager] Runtime asset registry is not registered: {type_id}")
            raise KeyError(type_id)
        registry.unregister(name)

    def get_or_create_runtime_asset(
        self,
        type_id: str,
        name: str,
        source_path: str | None = None,
        uuid: str | None = None,
        parent: Asset | None = None,
        parent_key: str | None = None,
    ):
        """Get or create a runtime asset through its plugin type registry."""
        registry = self._runtime_asset_registries.get(type_id)
        if registry is None:
            log.error(f"[AssetRuntimeManager] Runtime asset registry is not registered: {type_id}")
            raise KeyError(type_id)
        return registry.get_or_create_asset(
            name=name,
            source_path=source_path,
            uuid=uuid,
            parent=parent,
            parent_key=parent_key,
        )

    def get_or_create_embedded_asset(self, spec: EmbeddedAssetSpec):
        """Get or create an asset embedded inside another asset file."""
        if not spec.parent_key:
            log.error(
                f"[AssetRuntimeManager] Embedded asset '{spec.name}' "
                f"of type '{spec.type_id}' has an empty parent key"
            )
            raise ValueError("Embedded asset parent_key must be non-empty")

        return self.get_or_create_runtime_asset(
            spec.type_id,
            spec.name,
            source_path=spec.source_path,
            uuid=spec.uuid,
            parent=spec.parent,
            parent_key=spec.parent_key,
        )

    def get_asset_by_uuid(self, uuid: str) -> Asset | None:
        """Get any registered asset by UUID."""
        return self._assets_by_uuid.get(uuid)

    def register_file(self, result: "PreLoadResult") -> None:
        """Dispatch a preloaded file to the registered runtime asset plugin."""
        name = self._resource_name_from_preload_result(result)
        plugin = self._asset_type_plugins.get_runtime(result.resource_type)
        if plugin is None:
            log.error(
                f"[AssetRuntimeManager] No runtime asset plugin registered for type: {result.resource_type}"
            )
            return

        plugin.register(AssetContext(resource_manager=self, name=name), result)

    def reload_file(self, result: "PreLoadResult") -> bool:
        """Dispatch a preloaded file reload to the registered runtime asset plugin."""
        name = self._resource_name_from_preload_result(result)
        plugin = self._asset_type_plugins.get_runtime(result.resource_type)
        if plugin is None:
            log.error(
                f"[AssetRuntimeManager] No runtime asset plugin registered for reload type: {result.resource_type}"
            )
            return False

        try:
            reload_result = plugin.reload(AssetContext(resource_manager=self, name=name), result)
        except Exception:
            log.error(
                f"[AssetRuntimeManager] Runtime asset reload failed for type: {result.resource_type}",
                exc_info=True,
            )
            return False
        return reload_result is not False

    def unregister_file(self, result: "PreLoadResult") -> None:
        """Dispatch a preloaded file removal to the registered runtime asset plugin."""
        name = self._resource_name_from_preload_result(result)
        plugin = self._asset_type_plugins.get_runtime(result.resource_type)
        if plugin is None:
            log.error(
                f"[AssetRuntimeManager] No runtime asset plugin registered for unregister type: {result.resource_type}"
            )
            return

        if not isinstance(plugin, AssetRuntimeUnregisterPlugin):
            log.error(
                f"[AssetRuntimeManager] Runtime asset plugin does not support unregister: {result.resource_type}"
            )
            return

        plugin.unregister(AssetContext(resource_manager=self, name=name), result)

    def _resource_name_from_preload_result(self, result: "PreLoadResult") -> str:
        if result.resource_type == "glsl":
            return os.path.basename(result.path)
        return os.path.splitext(os.path.basename(result.path))[0]

    @classmethod
    def instance(cls) -> "AssetRuntimeManager":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.register_default_asset_type_plugins()
        return cls._instance

    @classmethod
    def _reset_for_testing(cls) -> None:
        cls._instance = None
