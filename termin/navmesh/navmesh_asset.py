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

    def load_from_content(
        self,
        content: str | None,
        has_uuid_in_spec: bool = False,
    ) -> bool:
        """
        Load navmesh from JSON content.

        Args:
            content: JSON content string
            has_uuid_in_spec: If True, spec file already has UUID (don't save)

        Returns:
            True if loaded successfully.
        """
        if content is None:
            return False

        try:
            from termin.navmesh.persistence import NavMeshPersistence

            self._navmesh = NavMeshPersistence.load_from_content(content)
            if self._navmesh is not None:
                self._navmesh.name = self._name
                self._loaded = True

                # Save spec file if no UUID was in spec
                if not has_uuid_in_spec and self._source_path:
                    self._save_spec_file()

                return True
        except Exception as e:
            print(f"[NavMeshAsset] Failed to load content: {e}")
        return False

    def _save_spec_file(self) -> bool:
        """Save UUID to spec file."""
        if self._source_path is None:
            return False

        from termin.editor.project_file_watcher import FilePreLoader

        spec_data = {"uuid": self.uuid}
        if FilePreLoader.write_spec_file(str(self._source_path), spec_data):
            self.mark_just_saved()
            print(f"[NavMeshAsset] Added UUID to spec: {self._name}")
            return True
        return False

    def unload(self) -> None:
        """Unload navmesh to free memory."""
        self._navmesh = None
        self._loaded = False

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
