"""VoxelGridAsset - Asset for voxel grid data."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin_assets import DataAsset

if TYPE_CHECKING:
    from termin.voxels.grid import VoxelGrid


class VoxelGridAsset(DataAsset["VoxelGrid"]):
    """
    Asset for voxel grid data.

    IMPORTANT: Create through ResourceManager, not directly.
    This ensures proper registration and avoids duplicates.

    Stores VoxelGrid (sparse voxel structure).
    """

    _uses_binary = False  # JSON text format

    def __init__(
        self,
        grid: "VoxelGrid | None" = None,
        name: str = "voxel_grid",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(data=grid, name=name, source_path=source_path, uuid=uuid)

    @property
    def grid(self) -> "VoxelGrid | None":
        """VoxelGrid data (lazy-loaded)."""
        return self.data

    @grid.setter
    def grid(self, value: "VoxelGrid | None") -> None:
        """Set grid and bump version."""
        self.data = value

    def parse_spec(self, spec_data: dict | None) -> None:
        super().parse_spec(spec_data)
        self._declare_runtime_resource()

    def _declare_runtime_resource(self) -> None:
        from termin.voxels._voxels_native import set_voxel_grid_asset_metadata

        source_path = self.source_path.as_posix() if self.source_path is not None else ""
        set_voxel_grid_asset_metadata(self.uuid, self.name, source_path)

    def _parse_content(self, content: str) -> "VoxelGrid | None":
        """Parse JSON content into VoxelGrid."""
        from termin.voxels.persistence import VoxelPersistence

        grid = VoxelPersistence.load_from_content(content)
        if grid is not None:
            grid.name = self._name
        return grid

    @classmethod
    def from_grid(
        cls,
        grid: "VoxelGrid",
        name: str | None = None,
        source_path: Path | str | None = None,
    ) -> "VoxelGridAsset":
        """Create VoxelGridAsset from existing VoxelGrid."""
        asset_name = name or grid.name or "voxel_grid"
        asset = cls(grid=grid, name=asset_name, source_path=source_path)
        asset._declare_runtime_resource()
        return asset
