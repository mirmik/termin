"""
VoxelGridKeeper и VoxelGridHandle — управление ссылками на воксельные сетки.

Наследуются от ResourceKeeper/ResourceHandle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.core.resource_handle import ResourceHandle, ResourceKeeper

if TYPE_CHECKING:
    from termin.voxels.grid import VoxelGrid


class VoxelGridKeeper(ResourceKeeper["VoxelGrid"]):
    """
    Владелец воксельной сетки по имени.

    VoxelGrid не требует GPU cleanup.
    """

    @property
    def grid(self) -> "VoxelGrid | None":
        """Алиас для resource."""
        return self._resource

    @property
    def has_grid(self) -> bool:
        """Алиас для has_resource."""
        return self.has_resource

    def set_grid(self, grid: "VoxelGrid", source_path: str | None = None) -> None:
        """Алиас для set_resource."""
        self.set_resource(grid, source_path)

    def update_grid(self, grid: "VoxelGrid") -> None:
        """Алиас для update_resource."""
        self.update_resource(grid)

    def _on_cleanup(self, resource: "VoxelGrid") -> None:
        """VoxelGrid не требует специальной очистки."""
        pass


class VoxelGridHandle(ResourceHandle["VoxelGrid"]):
    """
    Умная ссылка на воксельную сетку.

    Использование:
        handle = VoxelGridHandle.from_grid(grid)  # прямая ссылка
        handle = VoxelGridHandle.from_name("navmesh")  # по имени (hot-reload)
    """

    @classmethod
    def from_grid(cls, grid: "VoxelGrid") -> "VoxelGridHandle":
        """Создать handle с прямой ссылкой на сетку."""
        handle = cls()
        handle._init_direct(grid)
        return handle

    @classmethod
    def from_name(cls, name: str) -> "VoxelGridHandle":
        """Создать handle по имени сетки."""
        from termin.visualization.core.resources import ResourceManager

        handle = cls()
        keeper = ResourceManager.instance().get_or_create_voxel_grid_keeper(name)
        handle._init_named(name, keeper)
        return handle

    def serialize(self) -> dict:
        """Сериализация."""
        if self._direct is not None:
            return {
                "type": "direct",
                "name": self._direct.name if self._direct.name else None,
            }
        elif self._name is not None:
            return {
                "type": "named",
                "name": self._name,
            }
        else:
            return {"type": "none"}

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "VoxelGridHandle":
        """Десериализация."""
        handle_type = data.get("type", "none")

        if handle_type == "named":
            name = data.get("name")
            if name:
                return cls.from_name(name)
        elif handle_type == "direct":
            # Прямые ссылки на VoxelGrid не сериализуются полностью,
            # используем имя
            name = data.get("name")
            if name:
                return cls.from_name(name)

        return cls()
