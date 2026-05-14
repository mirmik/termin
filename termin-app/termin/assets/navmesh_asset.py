"""NavMeshAsset - Asset for navigation mesh data."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import TYPE_CHECKING

from termin.assets.data_asset import DataAsset

if TYPE_CHECKING:
    from termin.navmesh.types import NavMesh


@dataclass
class DetourNavMeshTileData:
    """Serialized Detour tile data stored in a Termin navmesh asset."""

    x: int
    y: int
    layer: int
    data: bytes


@dataclass
class DetourNavMeshData:
    """Detour-backed navmesh asset payload."""

    name: str
    agent_type: str
    coordinate_system: str
    build: dict
    tiles: list[DetourNavMeshTileData]

    def polygon_count(self) -> int:
        return 0

    def triangle_count(self) -> int:
        return 0

    def vertex_count(self) -> int:
        return 0


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
        data = json.loads(content)
        if data.get("format") == "termin.detour_navmesh":
            import base64

            tiles: list[DetourNavMeshTileData] = []
            for tile in data.get("tiles", []):
                encoding = tile.get("data_encoding", "base64")
                blob_text = tile.get("data", "")
                if encoding != "base64":
                    raise ValueError(f"Unsupported detour tile encoding: {encoding}")
                blob = base64.b64decode(blob_text)
                expected_size = int(tile.get("data_size", len(blob)))
                if expected_size != len(blob):
                    raise ValueError(
                        f"Detour tile size mismatch: expected {expected_size}, got {len(blob)}")
                tiles.append(DetourNavMeshTileData(
                    x=int(tile.get("x", 0)),
                    y=int(tile.get("y", 0)),
                    layer=int(tile.get("layer", 0)),
                    data=blob,
                ))

            return DetourNavMeshData(
                name=data.get("name", self._name),
                agent_type=data.get("agent_type", ""),
                coordinate_system=data.get("coordinate_system", ""),
                build=data.get("build", {}),
                tiles=tiles,
            )

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
