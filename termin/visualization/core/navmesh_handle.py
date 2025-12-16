"""
NavMeshHandle — умная ссылка на NavMeshAsset.

Указывает на NavMeshAsset напрямую или по имени через ResourceManager.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.core.resource_handle import ResourceHandle

if TYPE_CHECKING:
    from termin.navmesh.types import NavMesh
    from termin.navmesh.navmesh_asset import NavMeshAsset


def _get_navmesh_asset(name: str) -> "NavMeshAsset | None":
    """Lookup NavMeshAsset by name in ResourceManager."""
    from termin.visualization.core.resources import ResourceManager

    return ResourceManager.instance().get_navmesh_asset(name)


class NavMeshHandle(ResourceHandle["NavMeshAsset"]):
    """
    Умная ссылка на NavMeshAsset.

    Использование:
        handle = NavMeshHandle.from_asset(asset)      # прямая ссылка на asset
        handle = NavMeshHandle.from_navmesh(navmesh)  # прямая ссылка (создаёт asset)
        handle = NavMeshHandle.from_name("level1")    # по имени (hot-reload)
    """

    _resource_getter = staticmethod(_get_navmesh_asset)

    @classmethod
    def from_asset(cls, asset: "NavMeshAsset") -> "NavMeshHandle":
        """Создать handle с прямой ссылкой на NavMeshAsset."""
        handle = cls()
        handle._init_direct(asset)
        return handle

    @classmethod
    def from_navmesh(cls, navmesh: "NavMesh") -> "NavMeshHandle":
        """
        Создать handle из NavMesh (обратная совместимость).

        Создаёт NavMeshAsset из NavMesh.
        """
        from termin.navmesh.navmesh_asset import NavMeshAsset

        asset = NavMeshAsset.from_navmesh(navmesh)
        return cls.from_asset(asset)

    @classmethod
    def from_name(cls, name: str) -> "NavMeshHandle":
        """Создать handle по имени NavMesh."""
        handle = cls()
        handle._init_named(name)
        return handle

    # --- Convenience accessors ---

    def get_asset(self) -> "NavMeshAsset | None":
        """Получить NavMeshAsset."""
        return self.get()

    @property
    def asset(self) -> "NavMeshAsset | None":
        """Алиас для get()."""
        return self.get()

    def get_navmesh(self) -> "NavMesh | None":
        """
        Получить NavMesh.

        Returns:
            NavMesh или None если недоступен
        """
        asset = self.get()
        if asset is not None:
            return asset.navmesh
        return None

    def get_navmesh_or_none(self) -> "NavMesh | None":
        """Алиас для get_navmesh()."""
        return self.get_navmesh()

    # --- Serialization ---

    def serialize(self) -> dict:
        """Сериализация."""
        if self._direct is not None:
            return {
                "type": "direct",
                "name": self._direct.name,
            }
        elif self._name is not None:
            return {
                "type": "named",
                "name": self._name,
            }
        else:
            return {"type": "none"}

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "NavMeshHandle":
        """Десериализация."""
        handle_type = data.get("type", "none")

        if handle_type == "named":
            name = data.get("name")
            if name:
                return cls.from_name(name)
        elif handle_type == "direct":
            name = data.get("name")
            if name:
                return cls.from_name(name)

        return cls()
