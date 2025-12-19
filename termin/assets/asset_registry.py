"""
AssetRegistry — generic registry for assets.

Eliminates code duplication for asset management across different resource types.
"""

from __future__ import annotations

from typing import (
    Callable,
    Dict,
    Generic,
    Optional,
    TypeVar,
)

from termin.assets.asset import Asset

AssetT = TypeVar("AssetT", bound=Asset)  # Asset type (MeshAsset, TextureAsset, etc.)
DataT = TypeVar("DataT")  # Data/Handle type (MeshHandle, Material, VoxelGrid, etc.)


class AssetRegistry(Generic[AssetT, DataT]):
    """
    Generic registry for assets.

    Handles common operations:
    - get_asset(name) -> AssetT
    - register(name, asset, ...)
    - get(name) -> DataT (via data_from_asset callback)
    - list_names()
    - find_name(data)
    - find_uuid(data)
    - get_by_uuid(uuid) -> DataT
    - get_asset_by_uuid(uuid) -> AssetT
    - unregister(name)

    Type parameters:
        AssetT: Asset class (e.g., MeshAsset, TextureAsset)
        DataT: Data/Handle class returned by get() (e.g., MeshHandle, Material)
    """

    def __init__(
        self,
        asset_class: type[AssetT] | Callable[[], type[AssetT]],
        uuid_registry: Dict[str, Asset],
        data_from_asset: Callable[[AssetT], DataT | None],
        data_to_asset: Callable[[DataT], AssetT | None] | None = None,
    ):
        """
        Initialize registry.

        Args:
            asset_class: Asset class for isinstance checks, or a callable that returns it (for lazy loading)
            uuid_registry: Shared dict for UUID lookups (ResourceManager._assets_by_uuid)
            data_from_asset: Callback to extract Data/Handle from Asset
            data_to_asset: Optional callback to find Asset from Data (for find_name/find_uuid)
        """
        self._assets: Dict[str, AssetT] = {}
        self._asset_class_or_factory = asset_class
        self._asset_class_cached: type[AssetT] | None = None
        self._uuid_registry = uuid_registry
        self._data_from_asset = data_from_asset
        self._data_to_asset = data_to_asset

    @property
    def _asset_class(self) -> type[AssetT]:
        """Get asset class, resolving lazy factory if needed."""
        if self._asset_class_cached is None:
            if callable(self._asset_class_or_factory) and not isinstance(self._asset_class_or_factory, type):
                self._asset_class_cached = self._asset_class_or_factory()
            else:
                self._asset_class_cached = self._asset_class_or_factory
        return self._asset_class_cached

    @property
    def assets(self) -> Dict[str, AssetT]:
        """Direct access to assets dict."""
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
        """
        Get asset by name, creating it if it doesn't exist.

        This is the primary way to get assets - ensures single instance per name.

        Args:
            name: Resource name
            source_path: Source file path (for new assets)
            uuid: UUID (for new assets, from spec)
            parent: Parent asset (for embedded assets like mesh from GLB)
            parent_key: Key within parent (e.g., mesh name in GLB)
        """
        asset = self._assets.get(name)
        if asset is not None:
            return asset

        # Create new asset
        asset = self._asset_class(name=name, source_path=source_path, uuid=uuid)

        # Set parent for embedded assets
        if parent is not None and parent_key is not None:
            from termin.assets.data_asset import DataAsset
            if isinstance(asset, DataAsset):
                asset.set_parent(parent, parent_key)

        self._assets[name] = asset
        self._uuid_registry[asset.uuid] = asset
        return asset

    def register(
        self,
        name: str,
        asset: AssetT,
        source_path: str | None = None,
        uuid: str | None = None,
    ) -> None:
        """
        Register asset.

        Args:
            name: Resource name
            asset: Asset instance
            source_path: Optional source file path
            uuid: Optional fixed UUID (for builtins)
        """
        asset._name = name
        if source_path:
            asset._source_path = source_path
        if uuid is not None:
            asset._uuid = uuid
            asset._runtime_id = hash(uuid) & 0xFFFFFFFFFFFFFFFF

        self._assets[name] = asset
        self._uuid_registry[asset.uuid] = asset

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
                for name, a in self._assets.items():
                    if a is asset:
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
            if asset.uuid in self._uuid_registry:
                del self._uuid_registry[asset.uuid]
            del self._assets[name]

    def clear(self) -> None:
        """Remove all assets."""
        for asset in list(self._assets.values()):
            if asset.uuid in self._uuid_registry:
                del self._uuid_registry[asset.uuid]
        self._assets.clear()

    def __contains__(self, name: str) -> bool:
        """Check if name is registered."""
        return name in self._assets

    def __len__(self) -> int:
        """Number of registered assets."""
        return len(self._assets)
