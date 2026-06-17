"""Base smart reference for assets and direct resources."""

from __future__ import annotations

from typing import Callable, Generic, TypeVar

from termin_assets.asset import Asset

T = TypeVar("T")
AssetT = TypeVar("AssetT", bound=Asset)

_resource_manager_factory: Callable[[], object] | None = None


def set_resource_manager_factory(factory: Callable[[], object] | None) -> None:
    """Set factory used by ResourceHandle.from_name()."""
    global _resource_manager_factory
    _resource_manager_factory = factory


class ResourceHandle(Generic[T, AssetT]):
    """
    Base smart reference to a resource.

    Handles can store either a direct raw resource or an Asset wrapper.
    """

    _asset_getter: str = ""
    _asset_by_uuid_getter: str = ""

    def __init__(self):
        self._direct: T | None = None
        self._asset: AssetT | None = None

    @classmethod
    def from_name(cls, name: str) -> "ResourceHandle[T, AssetT]":
        """Create handle by name using the configured resource manager factory."""
        if not cls._asset_getter:
            return cls()
        if _resource_manager_factory is None:
            return cls()

        resource_manager = _resource_manager_factory()
        getter = getattr(resource_manager, cls._asset_getter, None)
        if getter is None:
            return cls()

        asset = getter(name)
        if asset is not None:
            return cls.from_asset(asset)
        return cls()

    @classmethod
    def from_asset(cls, asset: AssetT) -> "ResourceHandle[T, AssetT]":
        """Create handle with an Asset."""
        handle = cls()
        handle._init_asset(asset)
        return handle

    @classmethod
    def from_uuid(cls, uuid: str) -> "ResourceHandle[T, AssetT]":
        """Create handle by UUID using the configured resource manager factory."""
        if not cls._asset_by_uuid_getter:
            return cls()
        if _resource_manager_factory is None:
            return cls()

        resource_manager = _resource_manager_factory()
        getter = getattr(resource_manager, cls._asset_by_uuid_getter, None)
        if getter is None:
            return cls()

        asset = getter(uuid)
        if asset is not None:
            return cls.from_asset(asset)
        return cls()

    @property
    def is_direct(self) -> bool:
        """True if a direct raw object is stored."""
        return self._direct is not None

    @property
    def is_asset(self) -> bool:
        """True if an Asset is stored."""
        return self._asset is not None

    @property
    def name(self) -> str | None:
        """Resource name from Asset."""
        if self._asset is not None:
            return self._asset.name
        return None

    def get_asset(self) -> AssetT | None:
        """Get stored Asset."""
        return self._asset

    def get(self) -> T | None:
        """Get raw resource, if available."""
        if self._direct is not None:
            return self._direct
        if self._asset is not None:
            return self._get_resource_from_asset(self._asset)
        return None

    def _get_resource_from_asset(self, asset: AssetT) -> T | None:
        """Extract raw resource from Asset."""
        asset.ensure_loaded()
        return asset.resource

    def get_or_none(self) -> T | None:
        """Alias for get()."""
        return self.get()

    def _init_direct(self, resource: T) -> None:
        """Initialize with a direct raw object."""
        self._direct = resource
        self._asset = None

    def _init_asset(self, asset: AssetT) -> None:
        """Initialize with an Asset."""
        self._direct = None
        self._asset = asset

    def serialize(self) -> dict:
        """Serialize for scene saving."""
        if self._direct is not None:
            return self._serialize_direct()
        if self._asset is not None:
            result = {
                "uuid": self._asset.uuid,
                "name": self._asset.name,
            }
            if self._asset.source_path:
                result["type"] = "path"
                result["path"] = str(self._asset.source_path)
            else:
                result["type"] = "named"
            return result
        return {"type": "none"}

    def _serialize_direct(self) -> dict:
        """Serialize direct raw object. Subclasses should override."""
        return {"type": "direct_unsupported"}
