"""
VoxelGridHandle — умная ссылка на воксельную сетку.

Два режима:
1. Direct — хранит VoxelGrid напрямую
2. Asset — хранит VoxelGridAsset (lookup по имени через ResourceManager)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.assets.resource_handle import ResourceHandle

if TYPE_CHECKING:
    from termin.voxels.grid import VoxelGrid
    from termin.voxels.voxel_grid_asset import VoxelGridAsset


class VoxelGridHandle(ResourceHandle["VoxelGrid", "VoxelGridAsset"]):
    """
    Умная ссылка на воксельную сетку.

    Использование:
        handle = VoxelGridHandle.from_direct(grid)   # raw VoxelGrid
        handle = VoxelGridHandle.from_asset(asset)   # VoxelGridAsset
        handle = VoxelGridHandle.from_name("grid")   # lookup в ResourceManager
    """

    _asset_getter = "get_voxel_grid_asset"

    @classmethod
    def from_direct(cls, grid: "VoxelGrid") -> "VoxelGridHandle":
        """Создать handle с raw VoxelGrid."""
        handle = cls()
        handle._init_direct(grid)
        return handle

    # Alias for backward compatibility
    from_grid = from_direct

    # --- Convenience accessors ---

    @property
    def grid(self) -> "VoxelGrid | None":
        """Получить VoxelGrid."""
        return self.get()

    @property
    def asset(self) -> "VoxelGridAsset | None":
        """Получить VoxelGridAsset."""
        return self.get_asset()

    def get_grid(self) -> "VoxelGrid | None":
        """Получить VoxelGrid."""
        return self.get()

    def get_grid_or_none(self) -> "VoxelGrid | None":
        """Алиас для get_grid()."""
        return self.get()

    # --- Serialization ---

    def _serialize_direct(self) -> dict:
        """Сериализовать raw VoxelGrid."""
        # VoxelGrid сериализуется отдельно, здесь только ссылка
        return {"type": "direct_unsupported"}

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "VoxelGridHandle":
        """Десериализация."""
        handle_type = data.get("type", "none")

        if handle_type in ("named", "direct"):
            name = data.get("name")
            if name:
                return cls.from_name(name)

        return cls()
