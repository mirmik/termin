"""Generic base class for assets storing typed data."""

from __future__ import annotations

from abc import abstractmethod
from pathlib import Path
from typing import Generic, TypeVar

from tcbase import log

from termin_assets.asset import Asset

T = TypeVar("T")


class DataAsset(Asset, Generic[T]):
    """
    Generic base class for assets that store typed data.

    Subclasses must implement _parse_content().
    """

    _uses_binary: bool = False

    def __init__(
        self,
        data: T | None = None,
        name: str = "asset",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(name=name, source_path=source_path, uuid=uuid)
        self._data: T | None = data
        self._loaded = data is not None
        self._parent_asset: Asset | None = None
        self._parent_key: str | None = None
        self._has_uuid_in_spec: bool = False

    @property
    def data(self) -> T | None:
        """Get stored data, loading it if needed."""
        if not self._loaded:
            self._load()
        return self._data

    @data.setter
    def data(self, value: T | None) -> None:
        self._data = value
        self._loaded = value is not None
        self._bump_version()

    @property
    def cached_data(self) -> T | None:
        """Return cached data without triggering lazy loading."""
        return self._data

    @property
    def embedded_parent(self) -> Asset | None:
        """Parent asset that owns this embedded asset, if any."""
        return self._parent_asset

    @property
    def embedded_parent_key(self) -> str | None:
        """Stable key of this embedded asset inside its parent."""
        return self._parent_key

    def set_runtime_data(self, data: T | None, *, loaded: bool | None = None) -> None:
        """Set cached runtime data and explicit loaded state.

        This is the public replacement for callers that need to install a
        declared native handle while keeping the asset lazy.
        """
        self._data = data
        self._loaded = data is not None if loaded is None else loaded
        self._bump_version()

    @property
    def resource(self) -> T | None:
        """Underlying resource data."""
        return self.data

    def parse_spec(self, spec_data: dict | None) -> None:
        """Parse asset spec data and type-specific fields."""
        if spec_data is None:
            spec_data = {}

        spec_uuid = spec_data.get("uuid")
        if spec_uuid is not None:
            self._uuid = spec_uuid
            self._runtime_id = hash(self._uuid) & 0xFFFFFFFFFFFFFFFF
            self._has_uuid_in_spec = True

        self._parse_spec_fields(spec_data)

    def _parse_spec_fields(self, spec_data: dict) -> None:
        """Parse type-specific spec fields."""
        pass

    def _load(self) -> bool:
        """Load asset data from file or parent asset."""
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
            content = self._read_file()
            return self._load_content(content)
        except Exception:
            log.error(f"[{self.__class__.__name__}] Failed to load from {self._source_path}", exc_info=True)
            return False

    def _read_file(self) -> bytes | str:
        """Read file content according to _uses_binary."""
        if self._uses_binary:
            with open(self._source_path, "rb") as f:
                return f.read()
        with open(self._source_path, "r", encoding="utf-8") as f:
            return f.read()

    def _load_content(self, content: bytes | str) -> bool:
        """Parse content and set data."""
        try:
            self._data = self._parse_content(content)
            if self._data is not None:
                self._loaded = True
                self._on_loaded()
                if not self._has_uuid_in_spec and self._source_path:
                    self.save_spec_file()
                return True
        except Exception:
            log.error(f"[{self.__class__.__name__}] Failed to parse content: " + str(self.name), exc_info=True)
        return False

    @abstractmethod
    def _parse_content(self, content: bytes | str) -> T | None:
        """Parse raw content into a data object."""
        ...

    def _on_loaded(self) -> None:
        """Called after successful loading."""
        pass

    def _load_from_parent(self) -> bool:
        """Load data from parent asset."""
        if self._parent_asset is None:
            return False
        if not self._parent_asset.ensure_loaded():
            return False
        if self._loaded:
            return True

        log.debug(
            f"[LazyLoad] {self.__class__.__name__}: {self._name} "
            f"[{self._uuid[:8]}] (from {self._parent_asset._name})"
        )
        return self._extract_from_parent()

    def _extract_from_parent(self) -> bool:
        """Extract data from loaded parent."""
        return False

    def set_parent(self, parent: Asset, key: str) -> None:
        """Set parent asset for embedded assets."""
        self._parent_asset = parent
        self._parent_key = key

    def save_spec_file(self) -> bool:
        """Save spec file with UUID and type-specific settings."""
        if self._source_path is None:
            return False
        if self._parent_asset is not None:
            return False

        from termin_assets import write_spec_file

        spec_data = self._build_spec_data()
        if write_spec_file(str(self._source_path), spec_data):
            self.mark_just_saved()
            return True
        return False

    def _build_spec_data(self) -> dict:
        """Build spec data for saving."""
        return {"uuid": self.uuid}

    def unload(self) -> None:
        """Unload data to free memory."""
        self._data = None
        self._loaded = False

    def reload(self) -> bool:
        """Reload asset data from source_path."""
        if self._source_path is None:
            return False
        self.unload()
        result = self._load()
        if result:
            self._bump_version()
        return result

    def load_from_content(
        self,
        content: bytes | str | None,
        spec_data: dict | None = None,
    ) -> bool:
        """Load from already-read content."""
        if content is None:
            return False
        if spec_data is not None:
            self.parse_spec(spec_data)
        return self._load_content(content)
