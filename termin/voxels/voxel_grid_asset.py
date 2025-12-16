"""VoxelGridAsset - Asset for voxel grid data."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin.visualization.core.asset import Asset

if TYPE_CHECKING:
    from termin.voxels.grid import VoxelGrid


class VoxelGridAsset(Asset):
    """
    Asset for voxel grid data.

    Stores VoxelGrid (sparse voxel structure).
    """

    def __init__(
        self,
        grid: "VoxelGrid | None" = None,
        name: str = "voxel_grid",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        """
        Initialize VoxelGridAsset.

        Args:
            grid: VoxelGrid data (can be None for lazy loading)
            name: Human-readable name
            source_path: Path to source file for loading/reloading
            uuid: Existing UUID or None to generate new one
        """
        super().__init__(name=name, source_path=source_path, uuid=uuid)
        self._grid: "VoxelGrid | None" = grid
        self._loaded = grid is not None

    @property
    def grid(self) -> "VoxelGrid | None":
        """VoxelGrid data."""
        return self._grid

    @grid.setter
    def grid(self, value: "VoxelGrid | None") -> None:
        """Set grid and bump version."""
        self._grid = value
        self._loaded = value is not None
        self._bump_version()

    def load(self) -> bool:
        """
        Load voxel grid from source_path.

        Returns:
            True if loaded successfully.
        """
        if self._source_path is None:
            return False

        try:
            from termin.voxels.io import load_voxel_grid

            self._grid = load_voxel_grid(str(self._source_path))
            if self._grid is not None:
                self._grid.name = self._name
                self._loaded = True
                return True
        except Exception:
            pass
        return False

    def unload(self) -> None:
        """Unload grid to free memory."""
        self._grid = None
        self._loaded = False

    # --- Factory methods ---

    @classmethod
    def from_grid(
        cls,
        grid: "VoxelGrid",
        name: str | None = None,
        source_path: Path | str | None = None,
    ) -> "VoxelGridAsset":
        """Create VoxelGridAsset from existing VoxelGrid."""
        asset_name = name or grid.name or "voxel_grid"
        return cls(grid=grid, name=asset_name, source_path=source_path)
