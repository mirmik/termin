"""DataAsset - Generic base class for assets storing typed data."""

from __future__ import annotations

from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Generic, TypeVar

from termin.visualization.core.asset import Asset

if TYPE_CHECKING:
    pass

T = TypeVar("T")


class DataAsset(Asset, Generic[T]):
    """
    Generic base class for assets that store typed data.

    IMPORTANT: Assets should be created through ResourceManager, not directly.
    Use ResourceManager.get_or_create_*_asset() methods to ensure proper
    registration and avoid duplicate instances.

    Provides:
    - Immediate spec parsing (UUID, type-specific settings)
    - Lazy content loading
    - Support for embedded assets (e.g., meshes from GLB)

    Subclasses must implement:
    - _parse_content(): Parse raw content into data object
    - Optionally _parse_spec_fields(): Handle type-specific spec fields
    - Optionally _extract_from_parent(): For embedded assets
    """

    # Override in subclasses
    _uses_binary: bool = False

    def __init__(
        self,
        data: T | None = None,
        name: str = "asset",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        """
        Initialize DataAsset.

        Args:
            data: Initial data (can be None for lazy loading)
            name: Human-readable name
            source_path: Path to source file
            uuid: Existing UUID or None to generate new one
        """
        super().__init__(name=name, source_path=source_path, uuid=uuid)
        self._data: T | None = data
        self._loaded = data is not None

        # For embedded assets (e.g., mesh from GLB)
        self._parent_asset: "DataAsset | None" = None
        self._parent_key: str | None = None  # Key to identify this asset within parent

        # Track if UUID was in spec (to know if we need to save spec after loading)
        self._has_uuid_in_spec: bool = False

    # --- Data property ---

    @property
    def data(self) -> T | None:
        """Get the stored data (lazy loading)."""
        if not self._loaded:
            self.load()
        return self._data

    @data.setter
    def data(self, value: T | None) -> None:
        """Set data and bump version."""
        self._data = value
        self._loaded = value is not None
        self._bump_version()

    # --- Spec parsing (called immediately) ---

    def parse_spec(self, spec_data: dict | None) -> None:
        """
        Parse spec data. Called immediately after asset creation.

        Extracts UUID and type-specific settings from spec.
        Subclasses override _parse_spec_fields() for custom handling.

        Args:
            spec_data: Spec dictionary or None
        """
        if spec_data is None:
            return

        # Extract UUID from spec (if present)
        spec_uuid = spec_data.get("uuid")
        if spec_uuid is not None:
            self._uuid = spec_uuid
            self._runtime_id = hash(self._uuid) & 0xFFFFFFFFFFFFFFFF
            self._has_uuid_in_spec = True

        # Let subclass handle type-specific fields
        self._parse_spec_fields(spec_data)

    def _parse_spec_fields(self, spec_data: dict) -> None:
        """
        Parse type-specific spec fields. Override in subclasses.

        Args:
            spec_data: Spec dictionary (guaranteed non-None)
        """
        pass

    # --- Loading ---

    def load(self) -> bool:
        """
        Load asset data.

        For regular assets: loads from source_path.
        For embedded assets: extracts from parent.

        Returns:
            True if loaded successfully.
        """
        if self._loaded:
            return True

        if self._parent_asset is not None:
            return self._load_from_parent()
        return self._load_from_file()

    def _load_from_file(self) -> bool:
        """Load content from source file."""
        if self._source_path is None:
            return False

        try:
            print(f"[LazyLoad] {self.__class__.__name__}: {self._name}")
            content = self._read_file()
            return self._load_content(content)
        except Exception as e:
            print(f"[{self.__class__.__name__}] Failed to load from {self._source_path}: {e}")
            return False

    def _read_file(self) -> bytes | str:
        """Read file content (binary or text based on _uses_binary)."""
        if self._uses_binary:
            with open(self._source_path, "rb") as f:
                return f.read()
        else:
            with open(self._source_path, "r", encoding="utf-8") as f:
                return f.read()

    def _load_content(self, content: bytes | str) -> bool:
        """
        Parse content and set data.

        Args:
            content: Raw file content

        Returns:
            True if parsed successfully.
        """
        try:
            self._data = self._parse_content(content)
            if self._data is not None:
                self._loaded = True
                self._on_loaded()
                # Save spec file if UUID wasn't in spec (new asset)
                if not self._has_uuid_in_spec and self._source_path:
                    self.save_spec_file()
                return True
        except Exception as e:
            print(f"[{self.__class__.__name__}] Failed to parse content: {e}")
        return False

    @abstractmethod
    def _parse_content(self, content: bytes | str) -> T | None:
        """
        Parse raw content into data object. Must be implemented by subclasses.

        Args:
            content: Raw file content (bytes or str based on _uses_binary)

        Returns:
            Parsed data object or None on failure.
        """
        ...

    def _on_loaded(self) -> None:
        """
        Called after successful loading. Override for post-load actions.

        E.g., GLBAsset uses this to populate child assets with data.
        """
        pass

    # --- Embedded asset support ---

    def _load_from_parent(self) -> bool:
        """
        Load data from parent asset (for embedded assets).

        Ensures parent is loaded, then extracts this asset's portion.
        """
        if self._parent_asset is None:
            return False

        print(f"[LazyLoad] {self.__class__.__name__}: {self._name} (from {self._parent_asset._name})")

        # Ensure parent is loaded
        if not self._parent_asset.is_loaded:
            if not self._parent_asset.load():
                return False

        # Check if parent's _on_loaded() already populated this child
        if self._loaded:
            return True

        # Fallback: try to extract data (for subclasses that override this)
        return self._extract_from_parent()

    def _extract_from_parent(self) -> bool:
        """
        Extract data from loaded parent. Override in subclasses.

        Returns:
            True if extraction successful.
        """
        return False

    def set_parent(self, parent: "DataAsset", key: str) -> None:
        """
        Set parent asset for embedded assets.

        Args:
            parent: Parent asset containing this asset's data
            key: Key to identify this asset within parent (e.g., mesh name)
        """
        self._parent_asset = parent
        self._parent_key = key

    # --- Spec file persistence ---

    def save_spec_file(self) -> bool:
        """
        Save spec file with UUID and type-specific settings.

        Returns:
            True if saved successfully.
        """
        if self._source_path is None:
            return False

        # Don't save spec for embedded assets
        if self._parent_asset is not None:
            return False

        from termin.editor.project_file_watcher import FilePreLoader

        spec_data = self._build_spec_data()
        if FilePreLoader.write_spec_file(str(self._source_path), spec_data):
            self.mark_just_saved()
            return True
        return False

    def _build_spec_data(self) -> dict:
        """
        Build spec data for saving. Override to add type-specific fields.

        Returns:
            Spec dictionary with UUID and custom fields.
        """
        return {"uuid": self.uuid}

    # --- Unloading ---

    def unload(self) -> None:
        """Unload data to free memory."""
        self._data = None
        self._loaded = False

    # --- For backwards compatibility ---

    def load_from_content(
        self,
        content: bytes | str | None,
        spec_data: dict | None = None,
    ) -> bool:
        """
        Legacy method for loading from content.

        Prefer using parse_spec() + load() for new code.
        """
        if content is None:
            return False

        # Apply spec if provided
        if spec_data is not None:
            self.parse_spec(spec_data)

        # _load_content handles spec file saving if needed
        return self._load_content(content)
