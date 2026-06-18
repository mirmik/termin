"""Smart reference to a navmesh resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin_assets import ResourceHandle

if TYPE_CHECKING:
    from termin.default_assets.navmesh.asset import NavMeshAsset
    from termin.navmesh.types import NavMesh


class NavMeshHandle(ResourceHandle["NavMesh", "NavMeshAsset"]):
    """
    Smart reference to a navmesh.

    Usage:
        handle = NavMeshHandle.from_direct(navmesh)
        handle = NavMeshHandle.from_asset(asset)
        handle = NavMeshHandle.from_name("level1")
    """

    _asset_getter = "get_navmesh_asset"
    _asset_by_uuid_getter = "get_navmesh_asset_by_uuid"

    @classmethod
    def from_direct(cls, navmesh: "NavMesh") -> "NavMeshHandle":
        """Create handle with a raw NavMesh."""
        handle = cls()
        handle._init_direct(navmesh)
        return handle

    from_navmesh = from_direct

    @property
    def navmesh(self) -> "NavMesh | None":
        """Get NavMesh."""
        return self.get()

    @property
    def asset(self) -> "NavMeshAsset | None":
        """Get NavMeshAsset."""
        return self.get_asset()

    def get_navmesh(self) -> "NavMesh | None":
        """Get NavMesh."""
        return self.get()

    def get_navmesh_or_none(self) -> "NavMesh | None":
        """Alias for get_navmesh()."""
        return self.get()

    def _serialize_direct(self) -> dict:
        """Serialize raw NavMesh."""
        return {"type": "direct_unsupported"}

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "NavMeshHandle":
        """Deserialize."""
        uuid = data.get("uuid")
        if uuid:
            handle = cls.from_uuid(uuid)
            if handle.get_navmesh() is not None:
                return handle

        name = data.get("name")
        if name:
            return cls.from_name(name)

        return cls()
