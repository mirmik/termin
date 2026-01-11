"""
NavMeshHandle — умная ссылка на навигационную сетку.

Два режима:
1. Direct — хранит NavMesh напрямую
2. Asset — хранит NavMeshAsset (lookup по имени через ResourceManager)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.assets.resource_handle import ResourceHandle

if TYPE_CHECKING:
    from termin.navmesh.types import NavMesh
    from termin.navmesh.navmesh_asset import NavMeshAsset


class NavMeshHandle(ResourceHandle["NavMesh", "NavMeshAsset"]):
    """
    Умная ссылка на навигационную сетку.

    Использование:
        handle = NavMeshHandle.from_direct(navmesh)   # raw NavMesh
        handle = NavMeshHandle.from_asset(asset)      # NavMeshAsset
        handle = NavMeshHandle.from_name("level1")    # lookup в ResourceManager
    """

    _asset_getter = "get_navmesh_asset"

    @classmethod
    def from_uuid(cls, uuid: str) -> "NavMeshHandle":
        """Создать handle по UUID asset'а."""
        from termin.assets.resources import ResourceManager
        rm = ResourceManager.instance()
        asset = rm.get_navmesh_asset_by_uuid(uuid)
        if asset is not None:
            return cls.from_asset(asset)
        return cls()

    @classmethod
    def from_direct(cls, navmesh: "NavMesh") -> "NavMeshHandle":
        """Создать handle с raw NavMesh."""
        handle = cls()
        handle._init_direct(navmesh)
        return handle

    # Alias for backward compatibility
    from_navmesh = from_direct

    # --- Convenience accessors ---

    @property
    def navmesh(self) -> "NavMesh | None":
        """Получить NavMesh."""
        return self.get()

    @property
    def asset(self) -> "NavMeshAsset | None":
        """Получить NavMeshAsset."""
        return self.get_asset()

    def get_navmesh(self) -> "NavMesh | None":
        """Получить NavMesh."""
        return self.get()

    def get_navmesh_or_none(self) -> "NavMesh | None":
        """Алиас для get_navmesh()."""
        return self.get()

    # --- Serialization ---

    def _serialize_direct(self) -> dict:
        """Сериализовать raw NavMesh."""
        return {"type": "direct_unsupported"}

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "NavMeshHandle":
        """Десериализация."""
        # Сначала пробуем uuid (более надёжный способ)
        uuid = data.get("uuid")
        if uuid:
            handle = cls.from_uuid(uuid)
            if handle.get_navmesh() is not None:
                return handle

        # Затем пробуем по имени (UI и сцены передают name)
        name = data.get("name")
        if name:
            return cls.from_name(name)

        return cls()
