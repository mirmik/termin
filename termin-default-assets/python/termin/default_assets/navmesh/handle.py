"""Compatibility wrapper for navmesh runtime handles.

The canonical runtime resource is ``termin.navmesh._navmesh_native.TcNavMesh``.
This wrapper preserves the old Python ``NavMeshHandle`` API used by editor
components while keeping name/UUID lookup anchored in the C registry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from termin.default_assets.navmesh.asset import NavMeshAsset
    from termin.navmesh.types import NavMesh


def _empty_native():
    from termin.navmesh._navmesh_native import TcNavMesh

    return TcNavMesh()


def _native_from_uuid(uuid: str):
    from termin.navmesh._navmesh_native import TcNavMesh

    return TcNavMesh.from_uuid(uuid)


def _native_from_name(name: str):
    from termin.navmesh._navmesh_native import TcNavMesh

    return TcNavMesh.from_name(name)


def _native_declare(uuid: str, name: str = ""):
    from termin.navmesh._navmesh_native import TcNavMesh

    return TcNavMesh.declare(uuid, name)


class NavMeshHandle:
    """
    Backward-compatible smart reference for navmesh assets.

    New code that only needs the runtime resource should use ``TcNavMesh``
    directly. This class exists for Python/editor paths that still expect
    ``get_navmesh()`` to return the legacy polygon NavMesh asset payload.
    """

    def __init__(self, navmesh=None, *, asset: "NavMeshAsset | None" = None) -> None:
        self._native = navmesh if navmesh is not None else _empty_native()
        self._asset = asset
        self._direct: "NavMesh | None" = None

    @classmethod
    def from_name(cls, name: str) -> "NavMeshHandle":
        handle = cls(_native_from_name(name))
        asset = handle._asset_from_resource_manager(name=name)
        if asset is not None:
            handle._asset = asset
        if not handle.is_valid and asset is not None:
            return cls.from_asset(asset)
        return handle

    @classmethod
    def from_uuid(cls, uuid: str) -> "NavMeshHandle":
        handle = cls(_native_from_uuid(uuid))
        asset = handle._asset_from_resource_manager(uuid=uuid)
        if asset is not None:
            handle._asset = asset
        if not handle.is_valid and asset is not None:
            return cls.from_asset(asset)
        return handle

    @classmethod
    def from_asset(cls, asset: "NavMeshAsset") -> "NavMeshHandle":
        native = _native_declare(asset.uuid, asset.name)
        return cls(native, asset=asset)

    @classmethod
    def from_direct(cls, navmesh: "NavMesh") -> "NavMeshHandle":
        handle = cls()
        handle._direct = navmesh
        name = navmesh.name or ""
        if name:
            asset = handle._asset_from_resource_manager(name=name)
            if asset is not None:
                return cls.from_asset(asset)
        return handle

    from_navmesh = from_direct

    @property
    def native(self):
        """Return the canonical core ``TcNavMesh`` handle."""
        return self._native

    @property
    def is_valid(self) -> bool:
        return bool(self._native.is_valid) or self._direct is not None

    @property
    def name(self) -> str | None:
        native_name = self._native.name
        if native_name:
            return native_name
        asset = self.get_asset()
        if asset is not None:
            return asset.name
        if self._direct is not None:
            return self._direct.name
        return None

    @property
    def uuid(self) -> str | None:
        native_uuid = self._native.uuid
        if native_uuid:
            return native_uuid
        asset = self.get_asset()
        return asset.uuid if asset is not None else None

    @property
    def navmesh(self) -> "NavMesh | None":
        return self.get_navmesh()

    @property
    def asset(self) -> "NavMeshAsset | None":
        return self.get_asset()

    def get_asset(self) -> "NavMeshAsset | None":
        if self._asset is not None:
            return self._asset
        uuid = self._native.uuid
        name = self._native.name
        self._asset = self._asset_from_resource_manager(uuid=uuid or None, name=name or None)
        return self._asset

    def get(self) -> "NavMesh | None":
        return self.get_navmesh()

    def get_navmesh(self) -> "NavMesh | None":
        if self._direct is not None:
            return self._direct
        asset = self.get_asset()
        if asset is None:
            return None
        return asset.navmesh

    def get_navmesh_or_none(self) -> "NavMesh | None":
        return self.get_navmesh()

    def ensure_loaded(self) -> bool:
        if self._native.is_valid:
            return bool(self._native.ensure_loaded())
        asset = self.get_asset()
        if asset is not None:
            return bool(asset.ensure_loaded())
        return self._direct is not None

    def serialize(self) -> dict:
        uuid = self.uuid
        name = self.name
        if uuid:
            result = {"uuid": uuid}
            if name:
                result["name"] = name
            return result
        if name:
            return {"type": "named", "name": name}
        return {}

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "NavMeshHandle":
        uuid = data.get("uuid")
        if uuid:
            handle = cls.from_uuid(uuid)
            if handle.is_valid:
                return handle

        name = data.get("name")
        if name:
            return cls.from_name(name)

        return cls()

    @staticmethod
    def _asset_from_resource_manager(
        *,
        name: str | None = None,
        uuid: str | None = None,
    ) -> "NavMeshAsset | None":
        if not name and not uuid:
            return None
        from termin_assets import get_resource_manager

        resource_manager = get_resource_manager()
        if resource_manager is None:
            return None
        if uuid:
            asset = resource_manager.get_navmesh_asset_by_uuid(uuid)
            if asset is not None:
                return asset
        if name:
            return resource_manager.get_navmesh_asset(name)
        return None


__all__ = ["NavMeshHandle"]
