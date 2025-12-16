"""
VoxelGridHandle — умная ссылка на VoxelGridAsset.

Указывает на VoxelGridAsset напрямую или по имени через ResourceManager.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.core.resource_handle import ResourceHandle

if TYPE_CHECKING:
    from termin.voxels.grid import VoxelGrid
    from termin.voxels.voxel_grid_asset import VoxelGridAsset


def _get_voxel_grid_asset(name: str) -> "VoxelGridAsset | None":
    """Lookup VoxelGridAsset by name in ResourceManager."""
    from termin.visualization.core.resources import ResourceManager

    return ResourceManager.instance().get_voxel_grid_asset(name)


class VoxelGridHandle(ResourceHandle["VoxelGridAsset"]):
    """
    Умная ссылка на VoxelGridAsset.

    Использование:
        handle = VoxelGridHandle.from_asset(asset)  # прямая ссылка на asset
        handle = VoxelGridHandle.from_grid(grid)    # прямая ссылка (создаёт asset)
        handle = VoxelGridHandle.from_name("grid")  # по имени (hot-reload)
    """

    _resource_getter = staticmethod(_get_voxel_grid_asset)

    @classmethod
    def from_asset(cls, asset: "VoxelGridAsset") -> "VoxelGridHandle":
        """Создать handle с прямой ссылкой на VoxelGridAsset."""
        handle = cls()
        handle._init_direct(asset)
        return handle

    @classmethod
    def from_grid(cls, grid: "VoxelGrid") -> "VoxelGridHandle":
        """
        Создать handle из VoxelGrid (обратная совместимость).

        Создаёт VoxelGridAsset из VoxelGrid.
        """
        from termin.voxels.voxel_grid_asset import VoxelGridAsset

        asset = VoxelGridAsset.from_grid(grid)
        return cls.from_asset(asset)

    @classmethod
    def from_name(cls, name: str) -> "VoxelGridHandle":
        """Создать handle по имени сетки."""
        handle = cls()
        handle._init_named(name)
        return handle

    # --- Convenience accessors ---

    def get_asset(self) -> "VoxelGridAsset | None":
        """Получить VoxelGridAsset."""
        return self.get()

    @property
    def asset(self) -> "VoxelGridAsset | None":
        """Алиас для get()."""
        return self.get()

    def get_grid(self) -> "VoxelGrid | None":
        """
        Получить VoxelGrid.

        Returns:
            VoxelGrid или None если недоступен
        """
        asset = self.get()
        if asset is not None:
            return asset.grid
        return None

    def get_grid_or_none(self) -> "VoxelGrid | None":
        """Алиас для get_grid()."""
        return self.get_grid()

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
    def deserialize(cls, data: dict, context=None) -> "VoxelGridHandle":
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
