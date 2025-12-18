"""NavMeshAsset - Asset for navigation mesh data."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin.visualization.core.data_asset import DataAsset

if TYPE_CHECKING:
    from termin.navmesh.types import NavMesh


class NavMeshAsset(DataAsset["NavMesh"]):
    """
    Asset for navigation mesh data.

    IMPORTANT: Create through ResourceManager, not directly.
    This ensures proper registration and avoids duplicates.

    Stores NavMesh (polygons for pathfinding).
    """

    _uses_binary = False  # JSON text format

    def __init__(
        self,
        navmesh: "NavMesh | None" = None,
        name: str = "navmesh",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(data=navmesh, name=name, source_path=source_path, uuid=uuid)

    # --- Convenience property ---

    @property
    def navmesh(self) -> "NavMesh | None":
        """NavMesh data (lazy-loaded)."""
        return self.data

    @navmesh.setter
    def navmesh(self, value: "NavMesh | None") -> None:
        """Set navmesh and bump version."""
        self.data = value

    # --- Content parsing ---

    def _parse_content(self, content: str) -> "NavMesh | None":
        """Parse JSON content into NavMesh."""
        from termin.navmesh.persistence import NavMeshPersistence

        navmesh = NavMeshPersistence.load_from_content(content)
        if navmesh is not None:
            navmesh.name = self._name
        return navmesh

    # --- Factory methods ---

    @classmethod
    def from_navmesh(
        cls,
        navmesh: "NavMesh",
        name: str | None = None,
        source_path: Path | str | None = None,
    ) -> "NavMeshAsset":
        """Create NavMeshAsset from existing NavMesh."""
        asset_name = name or navmesh.name or "navmesh"
        return cls(navmesh=navmesh, name=asset_name, source_path=source_path)
