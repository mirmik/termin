"""
NavMeshKeeper и NavMeshHandle — управление ссылками на навигационные сетки.

Наследуются от ResourceKeeper/ResourceHandle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.core.resource_handle import ResourceHandle, ResourceKeeper

if TYPE_CHECKING:
    from termin.navmesh.types import NavMesh


class NavMeshKeeper(ResourceKeeper["NavMesh"]):
    """
    Владелец NavMesh по имени.

    NavMesh не требует GPU cleanup.
    """

    @property
    def navmesh(self) -> "NavMesh | None":
        """Алиас для resource."""
        return self._resource

    @property
    def has_navmesh(self) -> bool:
        """Алиас для has_resource."""
        return self.has_resource

    def set_navmesh(self, navmesh: "NavMesh", source_path: str | None = None) -> None:
        """Алиас для set_resource."""
        self.set_resource(navmesh, source_path)

    def update_navmesh(self, navmesh: "NavMesh") -> None:
        """Алиас для update_resource."""
        self.update_resource(navmesh)

    def _on_cleanup(self, resource: "NavMesh") -> None:
        """NavMesh не требует специальной очистки."""
        pass


class NavMeshHandle(ResourceHandle["NavMesh"]):
    """
    Умная ссылка на NavMesh.

    Использование:
        handle = NavMeshHandle.from_navmesh(navmesh)  # прямая ссылка
        handle = NavMeshHandle.from_name("level1_navmesh")  # по имени (hot-reload)
    """

    @classmethod
    def from_navmesh(cls, navmesh: "NavMesh") -> "NavMeshHandle":
        """Создать handle с прямой ссылкой на NavMesh."""
        handle = cls()
        handle._init_direct(navmesh)
        return handle

    @classmethod
    def from_name(cls, name: str) -> "NavMeshHandle":
        """Создать handle по имени NavMesh."""
        from termin.visualization.core.resources import ResourceManager

        handle = cls()
        keeper = ResourceManager.instance().get_or_create_navmesh_keeper(name)
        handle._init_named(name, keeper)
        return handle

    def serialize(self) -> dict:
        """Сериализация."""
        if self._direct is not None:
            return {
                "type": "direct",
                "name": None,
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
