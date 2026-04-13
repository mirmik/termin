"""
Project file watching system with pluggable file pre-loaders.

Provides centralized file watching for the editor with support for
different file types via FilePreLoader implementations.

PreLoaders don't parse files - they only:
- Determine file type
- Read UUID if possible (currently only .material files)
- Read file content (to avoid re-reading)
- Pass data to ResourceManager which creates/finds Asset and calls Asset.ensure_loaded()
"""

from __future__ import annotations

import os
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Dict, Set

from tcbase import log

if TYPE_CHECKING:
    from termin.visualization.core.resources import ResourceManager

# Debounce delay in seconds
DEBOUNCE_DELAY_S = 0.3


@dataclass
class PreLoadResult:
    """Result of pre-loading a file."""

    resource_type: str  # "material", "shader", "texture", "mesh", etc.
    path: str  # path to main file
    content: str | bytes | None = None  # file content (text or bytes)
    uuid: str | None = None  # UUID if found in file
    spec_data: dict | None = None  # data from .meta file if exists
    extra: dict = field(default_factory=dict)  # additional data


class FilePreLoader(ABC):
    """
    Abstract base class for file pre-loaders.

    PreLoaders detect file type, read UUID if possible, and pass
    data to ResourceManager. Actual parsing is done by Asset._load().
    """

    def __init__(
        self,
        resource_manager: "ResourceManager",
        on_resource_reloaded: Callable[[str, str], None] | None = None,
    ):
        self._resource_manager = resource_manager
        self._on_resource_reloaded = on_resource_reloaded
        # file_path -> set of resource names created from this file
        self._file_to_resources: Dict[str, Set[str]] = {}

    @property
    def priority(self) -> int:
        """
        Loading priority. Lower values are loaded first.

        Default priorities:
        - 0: shaders (no dependencies)
        - 10: textures (no dependencies)
        - 20: materials (depend on shaders, textures)
        - 30: other assets
        """
        return 30

    @property
    @abstractmethod
    def extensions(self) -> Set[str]:
        """
        Set of file extensions this pre-loader handles.
        Extensions include the dot, e.g., {'.material', '.shader'}.
        """
        ...

    @property
    @abstractmethod
    def resource_type(self) -> str:
        """
        Resource type name (e.g., 'material', 'shader', 'texture').
        """
        ...

    def preload(self, path: str) -> PreLoadResult | None:
        """
        Pre-load a file: read content, extract UUID if possible.

        Args:
            path: Path to the file

        Returns:
            PreLoadResult with file data, or None if not implemented.

        Note:
            Default returns None. Subclasses that use new PreLoadResult-based
            registration should override this. Legacy processors can override
            on_file_added/on_file_changed directly.
        """
        return None

    # --- Spec file helpers ---

    @staticmethod
    def read_spec_file(path: str) -> dict | None:
        """
        Read .meta file for a resource (with .spec fallback for migration).

        Args:
            path: Path to main resource file (e.g., "texture.png")

        Returns:
            Spec data dict or None if meta file doesn't exist.
        """
        import json

        # Try .meta first (new format)
        meta_path = path + ".meta"
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                log.warning(f"[ProjectFileWatcher] Failed to read meta file: {meta_path}", exc_info=True)

        # Fallback to .spec (old format, for migration)
        spec_path = path + ".spec"
        if os.path.exists(spec_path):
            try:
                with open(spec_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                log.warning(f"[ProjectFileWatcher] Failed to read spec file: {spec_path}", exc_info=True)

        return None

    @staticmethod
    def write_spec_file(path: str, data: dict) -> bool:
        """
        Write .meta file for a resource.

        Also removes old .spec file if it exists (automatic migration).

        Args:
            path: Path to main resource file (e.g., "texture.png")
            data: Spec data dict (must include "uuid")

        Returns:
            True if written successfully.
        """
        import json

        meta_path = path + ".meta"
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Remove old .spec file if exists (migration)
            old_spec_path = path + ".spec"
            if os.path.exists(old_spec_path):
                try:
                    os.remove(old_spec_path)
                except Exception:
                    log.warning(f"[ProjectFileWatcher] Failed to remove old spec file: {old_spec_path}", exc_info=True)

            return True
        except Exception:
            log.error(f"[ProjectFileWatcher] Failed to write meta file: {meta_path}", exc_info=True)
            return False

    @staticmethod
    def get_uuid_from_spec(path: str) -> str | None:
        """
        Get UUID from spec file.

        Args:
            path: Path to main resource file

        Returns:
            UUID string or None.
        """
        spec_data = FilePreLoader.read_spec_file(path)
        if spec_data:
            return spec_data.get("uuid")
        return None

    def on_file_added(self, path: str) -> None:
        """
        Called when a new file is detected.
        Pre-loads the file and registers with ResourceManager.
        """
        result = self.preload(path)
        if result is None:
            log.warn(f"[FilePreLoader] preload returned None for {path}")
            return

        name = os.path.splitext(os.path.basename(path))[0]

        # Register with ResourceManager (it will create/find Asset and call load)
        self._resource_manager.register_file(result)

        # Track file -> resource mapping
        if path not in self._file_to_resources:
            self._file_to_resources[path] = set()
        self._file_to_resources[path].add(name)

        self._notify_reloaded(name)

    def on_file_changed(self, path: str) -> None:
        """
        Called when an existing file is modified.
        Re-preloads the file and updates via ResourceManager.
        """
        result = self.preload(path)
        if result is None:
            return

        name = os.path.splitext(os.path.basename(path))[0]

        # ResourceManager handles reload logic
        self._resource_manager.reload_file(result)

        self._notify_reloaded(name)

    def on_file_removed(self, path: str) -> None:
        """
        Called when a file is deleted.
        Cleans up tracking.
        """
        if path in self._file_to_resources:
            del self._file_to_resources[path]

    def on_spec_changed(self, spec_path: str, resource_path: str) -> None:
        """
        Called when a .meta file for a resource changes.
        Triggers reload of the main resource.
        """
        if os.path.exists(resource_path):
            self.on_file_changed(resource_path)

    def get_file_count(self) -> int:
        """Returns number of tracked files."""
        return len(self._file_to_resources)

    def get_resource_count(self) -> int:
        """Returns total number of resources created from tracked files."""
        return sum(len(names) for names in self._file_to_resources.values())

    def get_tracked_files(self) -> Dict[str, Set[str]]:
        """Returns copy of file -> resources mapping."""
        return {path: names.copy() for path, names in self._file_to_resources.items()}

    def _notify_reloaded(self, resource_name: str) -> None:
        """Helper to call the reload callback."""
        if self._on_resource_reloaded is not None:
            self._on_resource_reloaded(self.resource_type, resource_name)


# Backward compatibility alias
FileTypeProcessor = FilePreLoader


class _WatchHandler:
    """watchdog event handler that enqueues changes for ProjectFileWatcher."""

    def __init__(self, watcher: ProjectFileWatcher) -> None:
        from watchdog.events import FileSystemEventHandler
        self._watcher = watcher
        self._base = FileSystemEventHandler()

    _RELEVANT_EVENTS = frozenset(("created", "modified", "deleted", "moved"))

    def dispatch(self, event) -> None:
        if event.is_directory:
            return
        etype = event.event_type
        if etype not in self._RELEVANT_EVENTS:
            return
        src = event.src_path
        if etype == "moved":
            self._watcher._enqueue_change(event.dest_path, "created")
            self._watcher._enqueue_change(src, "deleted")
        else:
            self._watcher._enqueue_change(src, etype)


class ProjectFileWatcher:
    """
    Central file watcher for project resources.

    Uses watchdog for live filesystem monitoring and os.walk for initial scan.
    Dispatches events to registered FilePreLoaders.
    """

    def __init__(
        self,
        on_resource_reloaded: Callable[[str, str], None] | None = None,
    ):
        self._observer = None  # watchdog Observer
        self._project_path: str | None = None
        self._watched_dirs: Set[str] = set()
        self._watched_files: Set[str] = set()

        # extension -> processor
        self._processors: Dict[str, FilePreLoader] = {}
        self._on_resource_reloaded = on_resource_reloaded

        # All project files by extension (for statistics)
        self._all_files_by_ext: Dict[str, Set[str]] = {}

        # Thread-safe pending changes from watchdog
        self._lock = threading.Lock()
        self._pending_changes: Dict[str, str] = {}  # path -> "created"/"modified"/"deleted"
        self._debounce_timer: threading.Timer | None = None

    def register_processor(self, processor: FilePreLoader) -> None:
        for ext in processor.extensions:
            if ext in self._processors:
                raise ValueError(f"Extension {ext} already registered")
            self._processors[ext] = processor

    def enable(self, project_path: str | None = None) -> None:
        """Enable file watching. Starts watchdog observer."""
        if project_path:
            self.watch_directory(project_path)

    def disable(self) -> None:
        """Stop watchdog observer and clear all state."""
        if self._debounce_timer is not None:
            self._debounce_timer.cancel()
            self._debounce_timer = None

        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2.0)
            self._observer = None

        self._project_path = None
        self._watched_dirs.clear()
        self._watched_files.clear()
        self._all_files_by_ext.clear()
        with self._lock:
            self._pending_changes.clear()

    def rescan(self) -> None:
        project_path = self._project_path
        if project_path is None:
            return

        for processor in self.get_all_processors():
            processor._file_to_resources.clear()

        self._watched_files.clear()
        self._all_files_by_ext.clear()

        self._scan_directory(project_path)

    def watch_directory(self, path: str) -> None:
        """Scan directory for resources and start live watching."""
        self._project_path = path

        if not os.path.exists(path):
            return

        # Synchronous scan
        self._scan_directory(path)

        # Start watchdog observer for live changes
        self._start_observer(path)

    def _scan_directory(self, path: str) -> None:
        """Recursively scan directory and process resource files."""
        pending_files: list[tuple[int, str, str]] = []

        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith((".", "__"))]
            self._watched_dirs.add(root)

            for filename in files:
                if filename.startswith("."):
                    continue

                file_path = os.path.join(root, filename)
                ext = os.path.splitext(filename)[1].lower()

                if ext:
                    if ext not in self._all_files_by_ext:
                        self._all_files_by_ext[ext] = set()
                    self._all_files_by_ext[ext].add(file_path)

                if ext in self._processors:
                    priority = self._processors[ext].priority
                    pending_files.append((priority, file_path, ext))
                elif ext in (".meta", ".spec"):
                    base_ext = self._get_spec_base_ext(file_path)
                    if base_ext and base_ext in self._processors:
                        priority = self._processors[base_ext].priority
                        pending_files.append((priority, file_path, ext))

        pending_files.sort(key=lambda x: (x[0], x[1]))

        for _priority, file_path, _ext in pending_files:
            self._add_file(file_path)

    def _start_observer(self, path: str) -> None:
        """Start watchdog observer for live file change detection."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2.0)
            self._observer = None

        try:
            from watchdog.observers import Observer

            handler = _WatchHandler(self)
            self._observer = Observer()
            self._observer.daemon = True
            self._observer.schedule(handler, path, recursive=True)
            self._observer.start()
        except Exception as e:
            log.error(f"[ProjectFileWatcher] Failed to start watchdog observer: {e}")

    def _enqueue_change(self, path: str, kind: str) -> None:
        """Called from watchdog thread. Enqueues change for poll() processing."""
        if not self._should_watch_file(path):
            return
        with self._lock:
            self._pending_changes[path] = kind
        # Restart debounce
        if self._debounce_timer is not None:
            self._debounce_timer.cancel()
        self._debounce_timer = threading.Timer(DEBOUNCE_DELAY_S, lambda: None)
        self._debounce_timer.daemon = True
        self._debounce_timer.start()

    def poll(self) -> None:
        """Process pending file changes. Call from main loop each frame."""
        if self._debounce_timer is not None and self._debounce_timer.is_alive():
            return  # Still debouncing
        with self._lock:
            if not self._pending_changes:
                return
            pending = dict(self._pending_changes)
            self._pending_changes.clear()
            if kind == "deleted":
                self._on_file_removed(path)
            elif kind == "created":
                if os.path.exists(path):
                    self._add_file(path)
            else:
                if os.path.exists(path):
                    self._on_file_changed(path)

    def _get_spec_base_ext(self, path: str) -> str | None:
        if path.endswith(".meta") or path.endswith(".spec"):
            base_path = path[:-5]
            return os.path.splitext(base_path)[1].lower() or None
        return None

    def _add_file(self, path: str) -> None:
        """Register a file with its processor."""
        self._watched_files.add(path)

        ext = os.path.splitext(path)[1].lower()

        if ext in (".meta", ".spec"):
            base_ext = self._get_spec_base_ext(path)
            if base_ext:
                processor = self._processors.get(base_ext)
                if processor is not None:
                    resource_path = path[:-5]
                    try:
                        processor.on_spec_changed(path, resource_path)
                    except Exception:
                        log.exception(f"[ProjectFileWatcher] Error processing meta {path}")
            return

        processor = self._processors.get(ext)
        if processor is not None:
            try:
                processor.on_file_added(path)
            except Exception:
                log.exception(f"[ProjectFileWatcher] Error processing {path}")

    def _should_watch_file(self, path: str) -> bool:
        ext = os.path.splitext(path)[1].lower()
        if ext in self._processors:
            return True
        if ext in (".meta", ".spec"):
            base_ext = self._get_spec_base_ext(path)
            return base_ext is not None and base_ext in self._processors
        return False

    def _on_file_removed(self, path: str) -> None:
        ext = os.path.splitext(path)[1].lower()
        processor = self._processors.get(ext)
        if processor is not None:
            processor.on_file_removed(path)
        self._watched_files.discard(path)

    def _on_file_changed(self, path: str) -> None:
        ext = os.path.splitext(path)[1].lower()

        if ext in (".meta", ".spec"):
            base_ext = self._get_spec_base_ext(path)
            if base_ext:
                processor = self._processors.get(base_ext)
                if processor is not None:
                    resource_path = path[:-5]
                    try:
                        processor.on_spec_changed(path, resource_path)
                    except Exception:
                        log.exception(f"[ProjectFileWatcher] Error processing meta {path}")
            return

        processor = self._processors.get(ext)
        if processor is not None:
            try:
                processor.on_file_changed(path)
            except Exception:
                log.exception(f"[ProjectFileWatcher] Error reloading {path}")

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_file_count(self, ext: str | None = None) -> int:
        if ext is None:
            return len(self._watched_files)
        return sum(
            1 for f in self._watched_files if os.path.splitext(f)[1].lower() == ext
        )

    def get_all_files_count(self) -> int:
        return sum(len(files) for files in self._all_files_by_ext.values())

    def get_all_files_by_extension(self) -> Dict[str, int]:
        stats = {ext: len(files) for ext, files in self._all_files_by_ext.items()}
        return dict(sorted(stats.items(), key=lambda x: (-x[1], x[0])))

    def get_stats(self) -> Dict[str, int]:
        stats: Dict[str, int] = {}
        seen_processors: Set[int] = set()
        for processor in self._processors.values():
            if id(processor) not in seen_processors:
                seen_processors.add(id(processor))
                stats[processor.resource_type] = processor.get_file_count()
        return stats

    def get_all_extensions(self) -> Set[str]:
        return set(self._processors.keys())

    def get_processor(self, ext: str) -> FilePreLoader | None:
        return self._processors.get(ext)

    def get_all_processors(self) -> list[FilePreLoader]:
        seen: Set[int] = set()
        result: list[FilePreLoader] = []
        for processor in self._processors.values():
            if id(processor) not in seen:
                seen.add(id(processor))
                result.append(processor)
        return result

    @property
    def project_path(self) -> str | None:
        return self._project_path

    @property
    def watched_dirs(self) -> Set[str]:
        return self._watched_dirs.copy()

    @property
    def watched_files(self) -> Set[str]:
        return self._watched_files.copy()

    @property
    def is_enabled(self) -> bool:
        return self._observer is not None
