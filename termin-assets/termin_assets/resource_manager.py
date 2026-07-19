"""Core asset runtime manager."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tcbase import log

from termin_assets.asset import Asset
from termin_assets.asset_store import AssetStore
from termin_assets.catalog import AssetCatalog
from termin_assets.default_plugins import register_default_asset_plugins
from termin_assets.embedded_asset import EmbeddedAssetSpec
from termin_assets.plugin import AssetContext, AssetRuntimeUnregisterPlugin, AssetTypeRegistry

if TYPE_CHECKING:
    from termin_assets.asset_registry import AssetRegistry
    from termin_assets.preload import PreLoadResult

from termin_assets.preload import AssetRegistration


@dataclass(frozen=True)
class AssetReloadEvent:
    """Typed notification emitted by one resource manager after a real reload."""

    type_id: str
    name: str
    uuid: str
    version: int


class AssetReloadSubscription:
    """Explicit lifetime token for a resource-manager-local reload listener."""

    def __init__(self, manager: "AssetRuntimeManager", subscription_id: int) -> None:
        self._manager: AssetRuntimeManager | None = manager
        self._subscription_id = subscription_id

    def close(self) -> None:
        manager = self._manager
        if manager is None:
            return
        manager._unsubscribe_asset_reloaded(self._subscription_id)
        self._manager = None


class AssetRuntimeManager:
    """Core asset runtime state and plugin dispatch.

    Domain-specific typed registries are registered by application/domain
    subclasses; this class owns only the shared plugin, UUID and external asset
    catalog mechanics.
    """

    _instance: "AssetRuntimeManager | None" = None

    def __init__(self) -> None:
        self._asset_store = AssetStore()
        self._asset_type_plugins = AssetTypeRegistry()
        self.external_assets = AssetCatalog()
        self._runtime_asset_registries: dict[str, "AssetRegistry"] = {}
        self._asset_reload_subscribers: dict[int, Callable[[AssetReloadEvent], None]] = {}
        self._next_asset_reload_subscription_id = 1

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

    def find_runtime_assets_by_name(self, type_id: str, name: str) -> tuple[Asset, ...]:
        """Return every runtime asset matching a non-unique display name."""
        registry = self._runtime_asset_registries.get(type_id)
        if registry is None:
            log.error(f"[AssetRuntimeManager] Runtime asset registry is not registered: {type_id}")
            return ()
        return registry.find_assets_by_name(name)

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

    def iter_runtime_assets(self, type_id: str) -> tuple[Asset, ...]:
        """Enumerate every typed asset by canonical UUID membership."""
        registry = self._runtime_asset_registries.get(type_id)
        if registry is None:
            log.error(f"[AssetRuntimeManager] Runtime asset registry is not registered: {type_id}")
            return ()
        return registry.iter_assets()

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

    def unregister_runtime_asset(
        self,
        type_id: str,
        name: str,
        *,
        uuid: str | None = None,
    ) -> Asset | None:
        """Remove a runtime asset, preferring canonical UUID when available."""
        registry = self._runtime_asset_registries.get(type_id)
        if registry is None:
            log.error(f"[AssetRuntimeManager] Runtime asset registry is not registered: {type_id}")
            raise KeyError(type_id)
        if uuid is not None:
            return registry.unregister_by_uuid(uuid)
        return registry.unregister(name)

    def unregister_runtime_asset_by_uuid(self, type_id: str, uuid: str) -> Asset | None:
        """Remove a runtime asset by canonical UUID."""
        registry = self._runtime_asset_registries.get(type_id)
        if registry is None:
            log.error(f"[AssetRuntimeManager] Runtime asset registry is not registered: {type_id}")
            raise KeyError(type_id)
        return registry.unregister_by_uuid(uuid)

    def rename_runtime_asset(self, type_id: str, uuid: str, name: str) -> bool:
        registry = self._runtime_asset_registries.get(type_id)
        if registry is None:
            log.error(f"[AssetRuntimeManager] Runtime asset registry is not registered: {type_id}")
            raise KeyError(type_id)
        return registry.rename(uuid, name)

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
        return self._asset_store.get(uuid)

    @property
    def assets_by_uuid(self):
        """Read-only view of canonical UUID-owned assets."""
        return self._asset_store.assets_by_uuid

    def register_file(self, result: "PreLoadResult") -> AssetRegistration | None:
        """Dispatch a preloaded file to the registered runtime asset plugin."""
        if not result.uuid:
            log.error(
                f"[AssetRuntimeManager] File registration requires UUID: "
                f"{result.resource_type} '{result.path}'"
            )
            return None
        name = self._resource_name_from_preload_result(result)
        plugin = self._asset_type_plugins.get_runtime(result.resource_type)
        if plugin is None:
            log.error(
                f"[AssetRuntimeManager] No runtime asset plugin registered for type: {result.resource_type}"
            )
            return None

        existing = self._asset_registration(result.resource_type, result.uuid)
        if existing is not None:
            existing_path = self._asset_source_path(result.resource_type, result.uuid)
            if existing_path is not None and os.path.abspath(existing_path) != os.path.abspath(result.path):
                log.error(
                    f"[AssetRuntimeManager] UUID collision for {result.resource_type} "
                    f"'{result.uuid}': '{existing_path}' vs '{result.path}'"
                )
                return None

        plugin.register(
            AssetContext(resource_manager=self, name=name, uuid=result.uuid),
            result,
        )
        registered = self._asset_registration(result.resource_type, result.uuid)
        if registered is None:
            log.error(
                f"[AssetRuntimeManager] Runtime plugin did not register UUID "
                f"'{result.uuid}' for {result.resource_type} '{result.path}'"
            )
        return registered

    def reload_file(
        self,
        result: "PreLoadResult",
        registration: AssetRegistration | None = None,
    ) -> bool:
        """Dispatch a preloaded file reload to the registered runtime asset plugin."""
        target = self._resolve_file_target(result, registration, operation="reload")
        if target is None:
            return False
        plugin = self._asset_type_plugins.get_runtime(result.resource_type)
        if plugin is None:
            log.error(
                f"[AssetRuntimeManager] No runtime asset plugin registered for reload type: {result.resource_type}"
            )
            return False

        asset_before = self._runtime_asset_by_uuid(target.type_id, target.uuid)
        version_before = asset_before.version if asset_before is not None else None
        try:
            reload_result = plugin.reload(
                AssetContext(resource_manager=self, name=target.name, uuid=target.uuid),
                result,
            )
        except Exception:
            log.error(
                f"[AssetRuntimeManager] Runtime asset reload failed for type: {result.resource_type}",
                exc_info=True,
            )
            return False
        if reload_result is False:
            return False

        asset_after = self._runtime_asset_by_uuid(target.type_id, target.uuid)
        if asset_before is not None and asset_after is not asset_before:
            log.error(
                f"[AssetRuntimeManager] Reload replaced asset identity for "
                f"{target.type_id} '{target.uuid}'"
            )
            return False
        if asset_after is not None and asset_after.version != version_before:
            self._publish_asset_reloaded(
                AssetReloadEvent(
                    type_id=result.resource_type,
                    name=asset_after.name,
                    uuid=asset_after.uuid,
                    version=asset_after.version,
                )
            )
        return True

    def subscribe_asset_reloaded(
        self,
        callback: Callable[[AssetReloadEvent], None],
    ) -> AssetReloadSubscription:
        """Subscribe to successful reloads from this manager only."""
        subscription_id = self._next_asset_reload_subscription_id
        self._next_asset_reload_subscription_id += 1
        self._asset_reload_subscribers[subscription_id] = callback
        return AssetReloadSubscription(self, subscription_id)

    def _publish_asset_reloaded(self, event: AssetReloadEvent) -> None:
        for callback in tuple(self._asset_reload_subscribers.values()):
            try:
                callback(event)
            except Exception:
                log.error(
                    f"[AssetRuntimeManager] Asset reload subscriber failed for "
                    f"{event.type_id} '{event.name}' ({event.uuid})",
                    exc_info=True,
                )

    def _unsubscribe_asset_reloaded(self, subscription_id: int) -> None:
        self._asset_reload_subscribers.pop(subscription_id, None)

    def unregister_file(
        self,
        result: "PreLoadResult",
        registration: AssetRegistration | None = None,
    ) -> bool:
        """Dispatch a preloaded file removal to the registered runtime asset plugin."""
        target = self._resolve_file_target(result, registration, operation="unregister")
        if target is None:
            return False
        plugin = self._asset_type_plugins.get_runtime(result.resource_type)
        if plugin is None:
            log.error(
                f"[AssetRuntimeManager] No runtime asset plugin registered for unregister type: {result.resource_type}"
            )
            return False

        if not isinstance(plugin, AssetRuntimeUnregisterPlugin):
            log.error(
                f"[AssetRuntimeManager] Runtime asset plugin does not support unregister: {result.resource_type}"
            )
            return False

        plugin.unregister(
            AssetContext(resource_manager=self, name=target.name, uuid=target.uuid),
            result,
        )
        if self._asset_registration(target.type_id, target.uuid) is not None:
            log.error(
                f"[AssetRuntimeManager] Runtime plugin did not unregister UUID "
                f"'{target.uuid}' for {target.type_id}"
            )
            return False
        return True

    def _resolve_file_target(
        self,
        result: "PreLoadResult",
        registration: AssetRegistration | None,
        *,
        operation: str,
    ) -> AssetRegistration | None:
        if not result.uuid:
            log.error(
                f"[AssetRuntimeManager] File {operation} requires UUID: "
                f"{result.resource_type} '{result.path}'"
            )
            return None
        if registration is not None and (
            registration.type_id != result.resource_type or registration.uuid != result.uuid
        ):
            log.error(
                f"[AssetRuntimeManager] Refusing {operation} identity change for '{result.path}': "
                f"registered={registration.type_id}:{registration.uuid}, "
                f"incoming={result.resource_type}:{result.uuid}"
            )
            return None
        target = self._asset_registration(result.resource_type, result.uuid)
        if target is None:
            log.error(
                f"[AssetRuntimeManager] Missing {operation} target for "
                f"{result.resource_type} UUID '{result.uuid}'"
            )
            return None
        if registration is not None and target != registration:
            log.error(
                f"[AssetRuntimeManager] Stale {operation} target for '{result.path}': "
                f"registered={registration}, current={target}"
            )
            return None
        return target

    def _asset_registration(self, type_id: str, uuid: str) -> AssetRegistration | None:
        asset = self._runtime_asset_by_uuid(type_id, uuid)
        if asset is not None:
            return AssetRegistration(type_id=type_id, uuid=uuid, name=asset.name)
        record = self.external_assets.get_by_uuid(type_id, uuid)
        if record is not None:
            return AssetRegistration(type_id=type_id, uuid=uuid, name=record.name)
        return None

    def _asset_source_path(self, type_id: str, uuid: str) -> str | None:
        asset = self._runtime_asset_by_uuid(type_id, uuid)
        if asset is not None and asset.source_path is not None:
            return str(asset.source_path)
        record = self.external_assets.get_by_uuid(type_id, uuid)
        return None if record is None else record.path

    def _runtime_asset_by_uuid(self, type_id: str, uuid: str) -> Asset | None:
        """Look up typed storage without treating external-only types as errors."""
        registry = self._runtime_asset_registries.get(type_id)
        return None if registry is None else registry.get_asset_by_uuid(uuid)

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
