"""NavMeshAsset - Asset for navigation mesh data."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin.visualization.core.asset import Asset

if TYPE_CHECKING:
    from termin.navmesh.types import NavMesh


class NavMeshAsset(Asset):
    """
    Asset for navigation mesh data.

    Stores NavMesh (polygons for pathfinding).
    """

    def __init__(
        self,
        navmesh: "NavMesh | None" = None,
        name: str = "navmesh",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        """
        Initialize NavMeshAsset.

        Args:
            navmesh: NavMesh data (can be None for lazy loading)
            name: Human-readable name
            source_path: Path to source file for loading/reloading
            uuid: Existing UUID or None to generate new one
        """
        super().__init__(name=name, source_path=source_path, uuid=uuid)
        self._navmesh: "NavMesh | None" = navmesh
        self._loaded = navmesh is not None

    @property
    def navmesh(self) -> "NavMesh | None":
        """NavMesh data."""
        return self._navmesh

    @navmesh.setter
    def navmesh(self, value: "NavMesh | None") -> None:
        """Set navmesh and bump version."""
        self._navmesh = value
        self._loaded = value is not None
        self._bump_version()

    def load(self) -> bool:
        """
        Load navmesh from source_path.

        Returns:
            True if loaded successfully.
        """
        if self._source_path is None:
            return False

        try:
            from termin.navmesh.io import load_navmesh

            self._navmesh = load_navmesh(str(self._source_path))
            if self._navmesh is not None:
                self._navmesh.name = self._name
                self._loaded = True
                return True
        except Exception:
            pass
        return False

    def unload(self) -> None:
        """Unload navmesh to free memory."""
        self._navmesh = None
        self._loaded = False

    # --- Serialization ---

    def serialize(self) -> dict:
        """Serialize navmesh asset reference."""
        return {
            "uuid": self.uuid,
            "name": self._name,
            "source_path": str(self._source_path) if self._source_path else None,
        }

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "NavMeshAsset":
        """Deserialize navmesh asset (lazy - doesn't load data)."""
        return cls(
            navmesh=None,
            name=data.get("name", "navmesh"),
            source_path=data.get("source_path"),
            uuid=data.get("uuid"),
        )

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
