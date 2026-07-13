"""Generic registry for assets."""

from __future__ import annotations

from typing import Callable, Dict, Generic, TypeVar

from tcbase import log

from termin_assets.asset import Asset

AssetT = TypeVar("AssetT", bound=Asset)
DataT = TypeVar("DataT")


class AssetRegistry(Generic[AssetT, DataT]):
    """Generic registry for asset wrappers and their data/handle values."""

    def __init__(
        self,
        asset_class: type[AssetT] | Callable[[], type[AssetT]],
        uuid_registry: Dict[str, Asset],
        data_from_asset: Callable[[AssetT], DataT | None],
        data_to_asset: Callable[[DataT], AssetT | None] | None = None,
    ):
        self._assets: Dict[str, AssetT] = {}
        self._asset_class_or_factory = asset_class
        self._asset_class_cached: type[AssetT] | None = None
        self._uuid_registry = uuid_registry
        self._data_from_asset = data_from_asset
        self._data_to_asset = data_to_asset

    @property
    def _asset_class(self) -> type[AssetT]:
        """Get asset class, resolving a lazy factory if needed."""
        if self._asset_class_cached is None:
            if callable(self._asset_class_or_factory) and not isinstance(self._asset_class_or_factory, type):
                self._asset_class_cached = self._asset_class_or_factory()
            else:
                self._asset_class_cached = self._asset_class_or_factory
        return self._asset_class_cached

    @property
    def assets(self) -> Dict[str, AssetT]:
        """Direct access to registered assets."""
        return self._assets

    def get_asset(self, name: str) -> AssetT | None:
        """Get asset by name."""
        return self._assets.get(name)

    def get_or_create_asset(
        self,
        name: str,
        source_path: str | None = None,
        uuid: str | None = None,
        parent: "Asset | None" = None,
        parent_key: str | None = None,
    ) -> AssetT:
        """Get asset by UUID/name or create a new one."""
        if uuid is not None:
            asset = self._uuid_registry.get(uuid)
            if asset is not None and isinstance(asset, self._asset_class):
                self._set_parent_if_applicable(asset, parent, parent_key)
                return asset

        if uuid is None:
            asset = self._assets.get(name)
            if asset is not None:
                self._set_parent_if_applicable(asset, parent, parent_key)
                return asset

        asset = self._asset_class(name=name, source_path=source_path, uuid=uuid)

        self._set_parent_if_applicable(asset, parent, parent_key)

        self._register_uuid(asset)
        self._assets[name] = asset
        return asset

    def _register_uuid(self, asset: AssetT) -> None:
        """Record an asset without allowing another asset to steal its UUID."""
        registered = self._uuid_registry.get(asset.uuid)
        if registered is not None and registered is not asset:
            log.error(
                f"[AssetRegistry] UUID collision for '{asset.uuid}': "
                f"cannot register '{asset.name}' over '{registered.name}'"
            )
            raise ValueError(f"Asset UUID is already registered: {asset.uuid}")
        self._uuid_registry[asset.uuid] = asset

    def _set_parent_if_applicable(
        self,
        asset: AssetT,
        parent: "Asset | None",
        parent_key: str | None,
    ) -> None:
        if parent is None or parent_key is None:
            return

        from termin_assets.data_asset import DataAsset

        if isinstance(asset, DataAsset):
            asset.set_parent(parent, parent_key)

    def register(
        self,
        name: str,
        asset: AssetT,
        source_path: str | None = None,
        uuid: str | None = None,
    ) -> None:
        """Register asset by name and UUID."""
        target_uuid = uuid if uuid is not None else asset.uuid
        registered = self._uuid_registry.get(target_uuid)
        if registered is not None and registered is not asset:
            log.error(
                f"[AssetRegistry] UUID collision for '{target_uuid}': "
                f"cannot register '{name}' over '{registered.name}'"
            )
            raise ValueError(f"Asset UUID is already registered: {target_uuid}")

        old_uuid = asset.uuid
        asset._name = name
        if source_path:
            asset.source_path = source_path
        if uuid is not None:
            asset._uuid = uuid
            asset._runtime_id = hash(uuid) & 0xFFFFFFFFFFFFFFFF

        if old_uuid != asset.uuid and self._uuid_registry.get(old_uuid) is asset:
            del self._uuid_registry[old_uuid]

        self._assets[name] = asset
        self._register_uuid(asset)

    def get(self, name: str) -> DataT | None:
        """Get data/handle by name."""
        asset = self._assets.get(name)
        if asset is None:
            return None
        return self._data_from_asset(asset)

    def list_names(self) -> list[str]:
        """List all registered names."""
        return sorted(self._assets.keys())

    def find_name(self, data: DataT) -> str | None:
        """Find name by data/handle."""
        if self._data_to_asset is not None:
            asset = self._data_to_asset(data)
            if asset is not None:
                for name, registered in self._assets.items():
                    if registered is asset:
                        return name
        return None

    def find_uuid(self, data: DataT) -> str | None:
        """Find UUID by data/handle."""
        if self._data_to_asset is not None:
            asset = self._data_to_asset(data)
            if asset is not None:
                return asset.uuid
        return None

    def get_by_uuid(self, uuid: str) -> DataT | None:
        """Get data/handle by UUID."""
        asset = self._uuid_registry.get(uuid)
        if asset is None or not isinstance(asset, self._asset_class):
            return None
        return self._data_from_asset(asset)

    def get_asset_by_uuid(self, uuid: str) -> AssetT | None:
        """Get asset by UUID."""
        asset = self._uuid_registry.get(uuid)
        if asset is None or not isinstance(asset, self._asset_class):
            return None
        return asset

    def unregister(self, name: str) -> None:
        """Remove asset by name."""
        asset = self._assets.get(name)
        if asset is not None:
            if self._uuid_registry.get(asset.uuid) is asset:
                del self._uuid_registry[asset.uuid]
            del self._assets[name]

    def clear(self) -> None:
        """Remove all assets."""
        for asset in list(self._assets.values()):
            if self._uuid_registry.get(asset.uuid) is asset:
                del self._uuid_registry[asset.uuid]
        self._assets.clear()

    def __contains__(self, name: str) -> bool:
        """Check if name is registered."""
        return name in self._assets

    def __len__(self) -> int:
        """Number of registered assets."""
        return len(self._assets)
