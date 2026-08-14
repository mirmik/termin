"""Canonical UUID-owned asset storage."""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from tcbase import log

from termin_assets.asset import Asset


class AssetStore:
    """Own registered assets by their immutable UUID identity."""

    def __init__(self) -> None:
        self._assets: dict[str, Asset] = {}

    @property
    def assets_by_uuid(self) -> Mapping[str, Asset]:
        """Read-only live view of canonical asset storage."""
        return MappingProxyType(self._assets)

    def get(self, uuid: str) -> Asset | None:
        return self._assets.get(uuid)

    def register(self, asset: Asset) -> None:
        registered = self._assets.get(asset.uuid)
        if registered is asset:
            return
        if registered is not None:
            log.error(
                f"[AssetStore] UUID collision for '{asset.uuid}': "
                f"cannot register '{asset.name}' over '{registered.name}'"
            )
            raise ValueError(f"Asset UUID is already registered: {asset.uuid}")
        asset._lock_identity()
        self._assets[asset.uuid] = asset

    def unregister(self, uuid: str, *, expected: Asset | None = None) -> Asset | None:
        registered = self._assets.get(uuid)
        if registered is None:
            return None
        if expected is not None and registered is not expected:
            log.error(
                f"[AssetStore] Refusing to unregister UUID '{uuid}' through a stale asset object"
            )
            return None
        del self._assets[uuid]
        return registered

    def clear(self) -> None:
        self._assets.clear()

    def __len__(self) -> int:
        return len(self._assets)
