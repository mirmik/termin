"""Typed UUID membership and name indexes for assets."""

from __future__ import annotations

from types import MappingProxyType
from typing import Callable, Generic, Mapping, TypeVar

from tcbase import log

from termin_assets.asset import Asset
from termin_assets.asset_store import AssetStore

AssetT = TypeVar("AssetT", bound=Asset)
DataT = TypeVar("DataT")


class AssetRegistry(Generic[AssetT, DataT]):
    """Typed view over an :class:`AssetStore` with ordered name buckets."""

    def __init__(
        self,
        asset_class: type[AssetT] | Callable[[], type[AssetT]],
        asset_store: AssetStore,
        data_from_asset: Callable[[AssetT], DataT | None],
        data_to_asset: Callable[[DataT], AssetT | None] | None = None,
    ):
        self._asset_uuids: dict[str, None] = {}
        self._uuids_by_name: dict[str, list[str]] = {}
        self._asset_class_or_factory = asset_class
        self._asset_class_cached: type[AssetT] | None = None
        self._asset_store = asset_store
        self._data_from_asset = data_from_asset
        self._data_to_asset = data_to_asset

    @property
    def _asset_class(self) -> type[AssetT]:
        if self._asset_class_cached is None:
            if callable(self._asset_class_or_factory) and not isinstance(
                self._asset_class_or_factory, type
            ):
                self._asset_class_cached = self._asset_class_or_factory()
            else:
                self._asset_class_cached = self._asset_class_or_factory
        return self._asset_class_cached

    @property
    def assets(self) -> Mapping[str, AssetT]:
        """Read-only UUID-keyed membership view.

        The returned mapping is a snapshot so callers cannot mutate registry
        membership or the canonical store behind its back.
        """
        return MappingProxyType({asset.uuid: asset for asset in self.iter_assets()})

    @property
    def unique_assets_by_name(self) -> Mapping[str, AssetT]:
        """Read-only compatibility view containing only unambiguous names."""
        return MappingProxyType(
            {
                name: asset
                for name, uuids in self._uuids_by_name.items()
                if len(uuids) == 1
                and (asset := self.get_asset_by_uuid(uuids[0])) is not None
            }
        )

    def iter_assets(self) -> tuple[AssetT, ...]:
        assets: list[AssetT] = []
        for uuid in self._asset_uuids:
            asset = self.get_asset_by_uuid(uuid)
            if asset is not None:
                assets.append(asset)
        return tuple(assets)

    def find_assets_by_name(self, name: str) -> tuple[AssetT, ...]:
        assets: list[AssetT] = []
        for uuid in self._uuids_by_name.get(name, ()):
            asset = self.get_asset_by_uuid(uuid)
            if asset is not None:
                assets.append(asset)
        return tuple(assets)

    def get_asset(self, name: str) -> AssetT | None:
        """Return the uniquely named asset, diagnosing ambiguity."""
        assets = self.find_assets_by_name(name)
        if len(assets) == 1:
            return assets[0]
        if len(assets) > 1:
            log.error(
                f"[AssetRegistry] Ambiguous asset name '{name}' matches UUIDs: "
                + ", ".join(asset.uuid for asset in assets)
            )
        return None

    def get_or_create_asset(
        self,
        name: str,
        source_path: str | None = None,
        uuid: str | None = None,
        parent: "Asset | None" = None,
        parent_key: str | None = None,
    ) -> AssetT:
        if uuid is not None:
            asset = self.get_asset_by_uuid(uuid)
            if asset is not None:
                if asset.name != name:
                    self.rename(uuid, name)
                self._set_parent_if_applicable(asset, parent, parent_key)
                return asset
        else:
            matches = self.find_assets_by_name(name)
            if len(matches) == 1:
                asset = matches[0]
                self._set_parent_if_applicable(asset, parent, parent_key)
                return asset
            if len(matches) > 1:
                log.error(
                    f"[AssetRegistry] Cannot get-or-create ambiguous asset name '{name}'"
                )
                raise ValueError(f"Asset name is ambiguous without UUID: {name}")

        asset = self._asset_class(name=name, source_path=source_path, uuid=uuid)
        self._set_parent_if_applicable(asset, parent, parent_key)
        self.register(name, asset)
        return asset

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
        """Register an asset without replacing UUID identity."""
        if not isinstance(asset, self._asset_class):
            raise TypeError(
                f"Expected {self._asset_class.__name__}, got {type(asset).__name__}"
            )
        if uuid is not None:
            try:
                asset._adopt_uuid(uuid)
            except ValueError:
                log.error(
                    f"[AssetRegistry] Cannot change registered UUID '{asset.uuid}' to '{uuid}'"
                )
                raise
        if asset._registry_owner is not None and asset._registry_owner is not self:
            log.error(
                f"[AssetRegistry] Asset UUID '{asset.uuid}' already belongs to another registry"
            )
            raise ValueError("Asset already belongs to another typed registry")

        self._asset_store.register(asset)
        asset._registry_owner = self
        if asset.uuid in self._asset_uuids:
            if asset.name != name:
                self.rename(asset.uuid, name)
        else:
            self._asset_uuids[asset.uuid] = None
            self._uuids_by_name.setdefault(name, []).append(asset.uuid)
            asset._rename(name)
        if source_path:
            asset.source_path = source_path

    def rename(self, uuid: str, name: str) -> bool:
        """Atomically move an asset between name buckets."""
        asset = self.get_asset_by_uuid(uuid)
        if asset is None:
            return False
        if asset.name == name:
            return True

        old_name = asset.name
        old_bucket = self._uuids_by_name[old_name]
        old_bucket.remove(uuid)
        if not old_bucket:
            del self._uuids_by_name[old_name]
        self._uuids_by_name.setdefault(name, []).append(uuid)
        asset._rename(name)
        return True

    def get(self, name: str) -> DataT | None:
        asset = self.get_asset(name)
        return None if asset is None else self._data_from_asset(asset)

    def list_names(self) -> list[str]:
        return sorted(self._uuids_by_name)

    def find_name(self, data: DataT) -> str | None:
        if self._data_to_asset is not None:
            asset = self._data_to_asset(data)
            if asset is not None and asset.uuid in self._asset_uuids:
                return asset.name
        return None

    def find_uuid(self, data: DataT) -> str | None:
        if self._data_to_asset is not None:
            asset = self._data_to_asset(data)
            if asset is not None and asset.uuid in self._asset_uuids:
                return asset.uuid
        return None

    def get_by_uuid(self, uuid: str) -> DataT | None:
        asset = self.get_asset_by_uuid(uuid)
        return None if asset is None else self._data_from_asset(asset)

    def get_asset_by_uuid(self, uuid: str) -> AssetT | None:
        if uuid not in self._asset_uuids:
            return None
        asset = self._asset_store.get(uuid)
        if asset is None or not isinstance(asset, self._asset_class):
            return None
        return asset

    def unregister_by_uuid(self, uuid: str) -> AssetT | None:
        asset = self.get_asset_by_uuid(uuid)
        if asset is None:
            return None
        bucket = self._uuids_by_name[asset.name]
        bucket.remove(uuid)
        if not bucket:
            del self._uuids_by_name[asset.name]
        del self._asset_uuids[uuid]
        self._asset_store.unregister(uuid, expected=asset)
        asset._registry_owner = None
        return asset

    def unregister(self, name: str) -> AssetT | None:
        asset = self.get_asset(name)
        if asset is None:
            return None
        return self.unregister_by_uuid(asset.uuid)

    def clear(self) -> None:
        for uuid in tuple(self._asset_uuids):
            self.unregister_by_uuid(uuid)

    def __contains__(self, name: str) -> bool:
        return bool(self._uuids_by_name.get(name))

    def __len__(self) -> int:
        return len(self._asset_uuids)
