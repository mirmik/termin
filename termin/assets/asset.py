"""Asset base class for all loadable resources."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin.core.identifiable import Identifiable

if TYPE_CHECKING:
    pass


class Asset(Identifiable):
    """
    Base class for all loadable resources.

    IMPORTANT: Assets should be created through ResourceManager, not directly.
    Use ResourceManager.get_or_create_*_asset() methods to ensure proper
    registration and avoid duplicate instances.

    Asset combines:
    - Identifiable (uuid, runtime_id)
    - Resource data management
    - Version tracking for GPU synchronization
    - Lazy loading support

    Subclasses implement specific resource types:
    - MeshAsset: stores Mesh3
    - TextureAsset: stores image data
    - MaterialAsset: stores material properties
    - etc.
    """

    def __init__(
        self,
        name: str,
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        """
        Initialize Asset.

        Args:
            name: Human-readable name for the asset
            source_path: Path to source file (for loading/reloading)
            uuid: Existing UUID or None to generate new one
        """
        super().__init__(uuid=uuid)
        self._name = name
        self._source_path: Path | None = Path(source_path) if source_path else None
        self._version: int = 0
        self._loaded: bool = False
        self._last_save_mtime: float | None = None  # mtime after internal save

    @property
    def name(self) -> str:
        """Human-readable name."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    @property
    def source_path(self) -> Path | None:
        """Path to source file."""
        return self._source_path

    @source_path.setter
    def source_path(self, value: Path | str | None) -> None:
        self._source_path = Path(value) if value else None

    @property
    def version(self) -> int:
        """
        Version counter for change tracking.

        Incremented when asset data changes.
        GPU wrappers use this to know when to re-upload.
        """
        return self._version

    @property
    def is_loaded(self) -> bool:
        """True if asset data is loaded."""
        return self._loaded

    def _bump_version(self) -> None:
        """Increment version counter. Call after modifying data."""
        self._version += 1

    def mark_just_saved(self) -> None:
        """
        Mark that the asset was just saved from within the application.

        Call this after saving to file. FileWatcher will then ignore
        the file change event since it's our own save, not external.
        """
        if self._source_path is not None and self._source_path.exists():
            self._last_save_mtime = self._source_path.stat().st_mtime

    def should_reload_from_file(self) -> bool:
        """
        Check if the file was modified externally and needs reload.

        Returns:
            True if file changed externally (not by our save), False otherwise.
        """
        if self._source_path is None or not self._source_path.exists():
            return False

        current_mtime = self._source_path.stat().st_mtime

        # If we just saved, check if mtime matches
        if self._last_save_mtime is not None:
            if current_mtime == self._last_save_mtime:
                # Our own save - reset flag and skip reload
                self._last_save_mtime = None
                return False
            else:
                # File was modified again after our save
                self._last_save_mtime = None
                return True

        # No recent save - this is external modification
        return True

    @property
    def resource(self):
        """
        Get the underlying resource data.

        Subclasses should override to return their specific data type.
        This provides a uniform interface for ResourceHandle.

        Returns:
            Resource data or None if not loaded.
        """
        return None

    def _load(self) -> bool:
        """
        Load asset data from source_path (internal).

        Override in subclasses to implement actual loading.

        Returns:
            True if loaded successfully, False otherwise.
        """
        if self._source_path is None:
            return False
        # Subclasses implement actual loading
        return False

    def ensure_loaded(self) -> bool:
        """
        Ensure asset is loaded. Call this for lazy loading.

        This is the primary public API for loading assets.

        Returns:
            True if asset is loaded (or was just loaded), False if loading failed.
        """
        if self._loaded:
            return True
        return self._load()

    def reload(self) -> bool:
        """
        Reload asset data from source_path (hot-reload).

        Returns:
            True if reloaded successfully, False otherwise.
        """
        if self._source_path is None:
            return False
        result = self._load()
        if result:
            self._bump_version()
        return result

    def unload(self) -> None:
        """
        Unload asset data to free memory.

        Override in subclasses to clear data.
        """
        self._loaded = False

    def serialize_ref(self) -> dict:
        """Serialize asset reference (uuid, name, source_path) for scene saving."""
        return {
            "uuid": self.uuid,
            "name": self._name,
            "source_path": str(self._source_path) if self._source_path else None,
        }

    @classmethod
    def deserialize_ref(cls, data: dict, context=None) -> "Asset":
        """
        Deserialize asset.

        Note: This creates an empty asset. Actual loading happens
        through ResourceManager or lazy loading.
        """
        return cls(
            name=data.get("name", "unnamed"),
            source_path=data.get("source_path"),
            uuid=data.get("uuid"),
        )
