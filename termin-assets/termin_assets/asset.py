"""Asset base class for loadable resources."""

from __future__ import annotations

from pathlib import Path
import threading
import time

from tcbase import log
from termin_assets.identifiable import Identifiable


class Asset(Identifiable):
    """
    Base class for loadable resources.

    Asset combines:
    - Identifiable (uuid, runtime_id)
    - Resource data management
    - Version tracking
    - Lazy loading support
    """

    def __init__(
        self,
        name: str,
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(uuid=uuid)
        self._name = name
        self._source_path: Path | None = Path(source_path) if source_path else None
        self._version: int = 0
        self._loaded: bool = False
        self._last_save_mtime: float | None = None
        self._registry_owner: object | None = None

    @property
    def name(self) -> str:
        """Human-readable name."""
        return self._name

    @name.setter
    def name(self, _value: str) -> None:
        raise AttributeError("Registered asset names must be changed through AssetRegistry.rename()")

    def _rename(self, value: str) -> None:
        """Update the display name after registry indexes have been prepared."""
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
        """Version counter for change tracking."""
        return self._version

    @property
    def is_loaded(self) -> bool:
        """True if asset data is loaded."""
        return self._loaded

    def _bump_version(self) -> None:
        """Increment version counter."""
        self._version += 1

    def mark_just_saved(self) -> None:
        """Mark that the asset was just saved by the application."""
        if self._source_path is not None and self._source_path.exists():
            self._last_save_mtime = self._source_path.stat().st_mtime

    def should_reload_from_file(self) -> bool:
        """Return true if source file changed externally and should reload."""
        if self._source_path is None or not self._source_path.exists():
            return False

        current_mtime = self._source_path.stat().st_mtime
        if self._last_save_mtime is not None:
            if current_mtime == self._last_save_mtime:
                self._last_save_mtime = None
                return False
            self._last_save_mtime = None
            return True

        return True

    @property
    def resource(self):
        """Underlying resource data, if loaded."""
        return None

    def _load(self) -> bool:
        """Load asset data. Subclasses implement actual loading."""
        if self._source_path is None:
            return False
        return False

    def ensure_loaded(self) -> bool:
        """Ensure asset data is loaded."""
        if self._loaded:
            return True
        return self._run_load_operation("load")

    def reload(self) -> bool:
        """Reload asset data from source_path."""
        if self._source_path is None:
            return False
        result = self._run_load_operation("reload")
        if result:
            self._bump_version()
        return result

    def unload(self) -> None:
        """Unload asset data."""
        self._loaded = False

    def _run_load_operation(self, operation: str) -> bool:
        started_at = time.perf_counter()
        thread_id = threading.get_ident()
        source_path = "" if self._source_path is None else str(self._source_path)
        type_name = type(self).__name__
        log.info(
            f"[AssetRuntimeLoad] begin operation={operation} type={type_name} "
            f"name='{self._name}' uuid='{self.uuid}' path='{source_path}' "
            f"thread={thread_id}"
        )
        try:
            result = bool(self._load())
        except Exception:
            log.error(
                f"[AssetRuntimeLoad] end operation={operation} type={type_name} "
                f"name='{self._name}' uuid='{self.uuid}' status=failed "
                f"duration_ms={(time.perf_counter() - started_at) * 1000.0:.3f} "
                f"path='{source_path}' thread={thread_id}",
                exc_info=True,
            )
            raise
        log.info(
            f"[AssetRuntimeLoad] end operation={operation} type={type_name} "
            f"name='{self._name}' uuid='{self.uuid}' "
            f"status={'ok' if result else 'failed'} "
            f"duration_ms={(time.perf_counter() - started_at) * 1000.0:.3f} "
            f"path='{source_path}' thread={thread_id}"
        )
        return result

    def serialize_ref(self) -> dict:
        """Serialize asset reference for scene saving."""
        return {
            "uuid": self.uuid,
            "name": self._name,
            "source_path": self._source_path.as_posix() if self._source_path else None,
        }

    @classmethod
    def deserialize_ref(cls, data: dict, context=None) -> "Asset":
        """Deserialize an asset reference."""
        return cls(
            name=data.get("name", "unnamed"),
            source_path=data.get("source_path"),
            uuid=data.get("uuid"),
        )
