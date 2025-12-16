"""
Project file watching system with pluggable file pre-loaders.

Provides centralized file watching for the editor with support for
different file types via FilePreLoader implementations.

PreLoaders don't parse files - they only:
- Determine file type
- Read UUID if possible (currently only .material files)
- Read file content (to avoid re-reading)
- Pass data to ResourceManager which creates/finds Asset and calls Asset.load()
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, Set

if TYPE_CHECKING:
    from PyQt6.QtCore import QFileSystemWatcher, QTimer
    from termin.visualization.core.resources import ResourceManager

# Debounce delay in milliseconds
DEBOUNCE_DELAY_MS = 300


@dataclass
class PreLoadResult:
    """Result of pre-loading a file."""

    resource_type: str  # "material", "shader", "texture", "mesh", etc.
    path: str  # path to main file
    content: str | bytes | None = None  # file content (text or bytes)
    uuid: str | None = None  # UUID if found in file
    spec_data: dict | None = None  # data from .spec file if exists
    extra: dict = field(default_factory=dict)  # additional data


class FilePreLoader(ABC):
    """
    Abstract base class for file pre-loaders.

    PreLoaders detect file type, read UUID if possible, and pass
    data to ResourceManager. Actual parsing is done by Asset.load().
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
        Read .spec file for a resource.

        Args:
            path: Path to main resource file (e.g., "texture.png")

        Returns:
            Spec data dict or None if spec file doesn't exist.
        """
        import json

        spec_path = path + ".spec"
        if not os.path.exists(spec_path):
            return None

        try:
            with open(spec_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    @staticmethod
    def write_spec_file(path: str, data: dict) -> bool:
        """
        Write .spec file for a resource.

        Args:
            path: Path to main resource file (e.g., "texture.png")
            data: Spec data dict (must include "uuid")

        Returns:
            True if written successfully.
        """
        import json

        spec_path = path + ".spec"
        try:
            with open(spec_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
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
        Called when a .spec file for a resource changes.
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


class ProjectFileWatcher:
    """
    Central file watcher for project resources.

    Owns QFileSystemWatcher, tracks all files by extension,
    and dispatches events to registered FilePreLoaders.
    """

    def __init__(
        self,
        on_resource_reloaded: Callable[[str, str], None] | None = None,
    ):
        self._file_watcher: "QFileSystemWatcher | None" = None
        self._project_path: str | None = None
        self._watched_dirs: Set[str] = set()
        self._watched_files: Set[str] = set()

        # extension -> processor
        self._processors: Dict[str, FilePreLoader] = {}
        self._on_resource_reloaded = on_resource_reloaded

        # All project files by extension (for statistics)
        self._all_files_by_ext: Dict[str, Set[str]] = {}  # ext -> set of paths

        # Debounce: pending file changes
        self._pending_changes: Set[str] = set()
        self._debounce_timer: "QTimer | None" = None

    def register_processor(self, processor: FilePreLoader) -> None:
        """
        Register a FilePreLoader for its extensions.

        Raises:
            ValueError: If extension already registered.
        """
        for ext in processor.extensions:
            if ext in self._processors:
                raise ValueError(f"Extension {ext} already registered")
            self._processors[ext] = processor

    def enable(self, project_path: str | None = None) -> None:
        """
        Enable file watching.

        Creates QFileSystemWatcher and starts monitoring project directory.
        """
        if self._file_watcher is not None:
            return

        from PyQt6.QtCore import QFileSystemWatcher, QTimer

        self._file_watcher = QFileSystemWatcher()
        self._file_watcher.directoryChanged.connect(self._on_directory_changed)
        self._file_watcher.fileChanged.connect(self._on_file_changed_debounced)

        # Debounce timer
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._process_pending_changes)

        if project_path:
            self.watch_directory(project_path)

    def disable(self) -> None:
        """Disable file watching and clear all state."""
        if self._debounce_timer is not None:
            self._debounce_timer.stop()
            self._debounce_timer = None

        if self._file_watcher is not None:
            self._file_watcher.directoryChanged.disconnect(self._on_directory_changed)
            self._file_watcher.fileChanged.disconnect(self._on_file_changed_debounced)
            self._file_watcher = None

        self._project_path = None
        self._watched_dirs.clear()
        self._watched_files.clear()
        self._all_files_by_ext.clear()
        self._pending_changes.clear()

    def rescan(self) -> None:
        """
        Rescan project directory for resources.

        Clears tracked files and re-processes all resource files.
        Used when resources need to be reloaded (e.g., after scene load).
        """
        project_path = self._project_path
        if project_path is None:
            return

        # Clear processor file tracking
        for processor in self.get_all_processors():
            processor._file_to_resources.clear()

        # Clear watched files (but keep directories)
        self._watched_files.clear()
        self._all_files_by_ext.clear()

        # Re-scan
        self.watch_directory(project_path)

    def watch_directory(self, path: str) -> None:
        """
        Recursively watch a directory for resource files.

        Files are collected first, then processed in priority order
        (lower priority values first) to handle dependencies correctly.
        """
        if self._file_watcher is None:
            return

        self._project_path = path

        if not os.path.exists(path):
            return

        # Collect all files first (before processing)
        # List of (priority, file_path, ext)
        pending_files: list[tuple[int, str, str]] = []

        # Walk directory tree
        for root, dirs, files in os.walk(path):
            # Skip hidden and __pycache__ directories
            dirs[:] = [d for d in dirs if not d.startswith((".", "__"))]

            # Watch directory
            if root not in self._watched_dirs:
                self._file_watcher.addPath(root)
                self._watched_dirs.add(root)

            # Collect all files
            for filename in files:
                # Skip hidden files
                if filename.startswith("."):
                    continue

                file_path = os.path.join(root, filename)
                ext = os.path.splitext(filename)[1].lower()

                # Track all files for statistics
                if ext:  # Only files with extension
                    if ext not in self._all_files_by_ext:
                        self._all_files_by_ext[ext] = set()
                    self._all_files_by_ext[ext].add(file_path)

                # Queue resource files for processing
                if ext in self._processors:
                    priority = self._processors[ext].priority
                    pending_files.append((priority, file_path, ext))
                # Also queue .spec files for known resource types
                elif ext == ".spec":
                    base_ext = self._get_spec_base_ext(file_path)
                    if base_ext and base_ext in self._processors:
                        priority = self._processors[base_ext].priority
                        pending_files.append((priority, file_path, ext))

        # Sort by priority (lower first), then by path for deterministic order
        pending_files.sort(key=lambda x: (x[0], x[1]))

        # Process files in priority order
        for _priority, file_path, _ext in pending_files:
            self._add_file(file_path)

    def _get_spec_base_ext(self, path: str) -> str | None:
        """
        For a .spec file, return the base file's extension.

        Example: "model.stl.spec" -> ".stl", "image.png.spec" -> ".png"
        Returns None if not a spec file or base extension unknown.
        """
        if not path.endswith(".spec"):
            return None
        base_path = path[:-5]  # Remove ".spec"
        return os.path.splitext(base_path)[1].lower() or None

    def _add_file(self, path: str) -> None:
        """Add a file to watching and notify processor."""
        if self._file_watcher is None:
            return

        if path not in self._watched_files:
            self._file_watcher.addPath(path)
            self._watched_files.add(path)

        ext = os.path.splitext(path)[1].lower()

        # Handle .spec files specially
        if ext == ".spec":
            base_ext = self._get_spec_base_ext(path)
            if base_ext:
                processor = self._processors.get(base_ext)
                if processor is not None:
                    resource_path = path[:-5]
                    try:
                        processor.on_spec_changed(path, resource_path)
                    except Exception as e:
                        print(f"[ProjectFileWatcher] Error processing spec {path}: {e}")
            return

        processor = self._processors.get(ext)
        if processor is not None:
            try:
                processor.on_file_added(path)
            except Exception as e:
                print(f"[ProjectFileWatcher] Error processing {path}: {e}")

    def _should_watch_file(self, path: str) -> bool:
        """Check if file should be watched (resource or spec file)."""
        ext = os.path.splitext(path)[1].lower()
        if ext in self._processors:
            return True
        # Also watch .spec files for known resource types
        if ext == ".spec":
            base_ext = self._get_spec_base_ext(path)
            return base_ext is not None and base_ext in self._processors
        return False

    def _on_directory_changed(self, path: str) -> None:
        """Handle directory changes (new files)."""
        if self._file_watcher is None:
            return

        try:
            entries = os.listdir(path)
        except OSError:
            # Directory may have been deleted
            return

        for filename in entries:
            file_path = os.path.join(path, filename)

            if os.path.isdir(file_path):
                # New subdirectory
                if file_path not in self._watched_dirs and not filename.startswith(
                    (".", "__")
                ):
                    self._file_watcher.addPath(file_path)
                    self._watched_dirs.add(file_path)
            else:
                if self._should_watch_file(file_path) and file_path not in self._watched_files:
                    self._add_file(file_path)

    def _on_file_changed_debounced(self, path: str) -> None:
        """Handle file change with debouncing."""
        # QFileSystemWatcher may remove path after change (Linux quirk)
        if self._file_watcher is not None and os.path.exists(path):
            if path not in self._file_watcher.files():
                self._file_watcher.addPath(path)

        # Add to pending and restart timer
        self._pending_changes.add(path)
        if self._debounce_timer is not None:
            self._debounce_timer.start(DEBOUNCE_DELAY_MS)

    def _process_pending_changes(self) -> None:
        """Process all pending file changes after debounce delay."""
        pending = self._pending_changes.copy()
        self._pending_changes.clear()

        for path in pending:
            if not os.path.exists(path):
                continue
            self._on_file_changed(path)

    def _on_file_changed(self, path: str) -> None:
        """Handle file modification (actual processing)."""
        ext = os.path.splitext(path)[1].lower()

        # Handle .spec files specially
        if ext == ".spec":
            base_ext = self._get_spec_base_ext(path)
            if base_ext:
                processor = self._processors.get(base_ext)
                if processor is not None:
                    resource_path = path[:-5]
                    try:
                        processor.on_spec_changed(path, resource_path)
                    except Exception as e:
                        print(f"[ProjectFileWatcher] Error processing spec {path}: {e}")
            return

        processor = self._processors.get(ext)
        if processor is not None:
            try:
                processor.on_file_changed(path)
            except Exception as e:
                print(f"[ProjectFileWatcher] Error reloading {path}: {e}")

    # Statistics methods

    def get_file_count(self, ext: str | None = None) -> int:
        """
        Get count of watched files (files with registered processors).

        Args:
            ext: Filter by extension (e.g., '.material'). None for all watched files.
        """
        if ext is None:
            return len(self._watched_files)

        return sum(
            1 for f in self._watched_files if os.path.splitext(f)[1].lower() == ext
        )

    def get_all_files_count(self) -> int:
        """Get total count of all project files."""
        return sum(len(files) for files in self._all_files_by_ext.values())

    def get_all_files_by_extension(self) -> Dict[str, int]:
        """
        Get statistics of all project files by extension.

        Returns:
            Dict mapping extension (e.g., '.py') to file count, sorted by count descending.
        """
        stats = {ext: len(files) for ext, files in self._all_files_by_ext.items()}
        # Sort by count descending, then by extension
        return dict(sorted(stats.items(), key=lambda x: (-x[1], x[0])))

    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics by resource type.

        Returns:
            Dict mapping resource_type to file count.
        """
        stats: Dict[str, int] = {}
        # Deduplicate processors (same processor may handle multiple extensions)
        seen_processors: Set[int] = set()
        for processor in self._processors.values():
            if id(processor) not in seen_processors:
                seen_processors.add(id(processor))
                stats[processor.resource_type] = processor.get_file_count()
        return stats

    def get_all_extensions(self) -> Set[str]:
        """Get all registered extensions."""
        return set(self._processors.keys())

    def get_processor(self, ext: str) -> FilePreLoader | None:
        """Get processor for extension."""
        return self._processors.get(ext)

    def get_all_processors(self) -> list[FilePreLoader]:
        """Get list of unique processors."""
        seen: Set[int] = set()
        result: list[FilePreLoader] = []
        for processor in self._processors.values():
            if id(processor) not in seen:
                seen.add(id(processor))
                result.append(processor)
        return result

    @property
    def project_path(self) -> str | None:
        """Current project path being watched."""
        return self._project_path

    @property
    def watched_dirs(self) -> Set[str]:
        """Set of watched directories (read-only copy)."""
        return self._watched_dirs.copy()

    @property
    def watched_files(self) -> Set[str]:
        """Set of watched files (read-only copy)."""
        return self._watched_files.copy()

    @property
    def is_enabled(self) -> bool:
        """Whether file watching is enabled."""
        return self._file_watcher is not None
