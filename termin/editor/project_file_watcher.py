"""
Project file watching system with pluggable file type processors.

Provides centralized file watching for the editor with support for
different file types via FileTypeProcessor implementations.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable, Dict, Set

if TYPE_CHECKING:
    from PyQt6.QtCore import QFileSystemWatcher
    from termin.visualization.core.resources import ResourceManager


class FileTypeProcessor(ABC):
    """
    Abstract base class for file type handlers.

    Each processor handles specific file extensions and notifies
    ResourceManager when files are added, changed, or removed.
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
        Set of file extensions this processor handles.
        Extensions include the dot, e.g., {'.material', '.shader'}.
        """
        ...

    @property
    @abstractmethod
    def resource_type(self) -> str:
        """
        Resource type name for callbacks (e.g., 'material', 'shader', 'texture').
        """
        ...

    @abstractmethod
    def on_file_added(self, path: str) -> None:
        """
        Called when a new file is detected.
        Should load the resource and register it with ResourceManager.
        """
        ...

    @abstractmethod
    def on_file_changed(self, path: str) -> None:
        """
        Called when an existing file is modified.
        Should reload the resource in ResourceManager.
        """
        ...

    @abstractmethod
    def on_file_removed(self, path: str) -> None:
        """
        Called when a file is deleted.
        Should handle cleanup if needed.
        """
        ...

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


class ProjectFileWatcher:
    """
    Central file watcher for project resources.

    Owns QFileSystemWatcher, tracks all files by extension,
    and dispatches events to registered FileTypeProcessors.
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
        self._processors: Dict[str, FileTypeProcessor] = {}
        self._on_resource_reloaded = on_resource_reloaded

        # All project files by extension (for statistics)
        self._all_files_by_ext: Dict[str, Set[str]] = {}  # ext -> set of paths

    def register_processor(self, processor: FileTypeProcessor) -> None:
        """
        Register a FileTypeProcessor for its extensions.

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

        from PyQt6.QtCore import QFileSystemWatcher

        self._file_watcher = QFileSystemWatcher()
        self._file_watcher.directoryChanged.connect(self._on_directory_changed)
        self._file_watcher.fileChanged.connect(self._on_file_changed)

        if project_path:
            self.watch_directory(project_path)

    def disable(self) -> None:
        """Disable file watching and clear all state."""
        if self._file_watcher is not None:
            self._file_watcher.directoryChanged.disconnect(self._on_directory_changed)
            self._file_watcher.fileChanged.disconnect(self._on_file_changed)
            self._file_watcher = None

        self._project_path = None
        self._watched_dirs.clear()
        self._watched_files.clear()
        self._all_files_by_ext.clear()

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

        # Sort by priority (lower first), then by path for deterministic order
        pending_files.sort(key=lambda x: (x[0], x[1]))

        # Process files in priority order
        for _priority, file_path, _ext in pending_files:
            self._add_file(file_path)

    def _add_file(self, path: str) -> None:
        """Add a file to watching and notify processor."""
        if self._file_watcher is None:
            return

        if path not in self._watched_files:
            self._file_watcher.addPath(path)
            self._watched_files.add(path)

        ext = os.path.splitext(path)[1].lower()
        processor = self._processors.get(ext)
        if processor is not None:
            try:
                processor.on_file_added(path)
            except Exception as e:
                print(f"[ProjectFileWatcher] Error processing {path}: {e}")

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
                ext = os.path.splitext(filename)[1].lower()
                if ext in self._processors and file_path not in self._watched_files:
                    self._add_file(file_path)

    def _on_file_changed(self, path: str) -> None:
        """Handle file modifications."""
        # QFileSystemWatcher may remove path after change (Linux quirk)
        if self._file_watcher is not None and os.path.exists(path):
            if path not in self._file_watcher.files():
                self._file_watcher.addPath(path)

        ext = os.path.splitext(path)[1].lower()
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

    def get_processor(self, ext: str) -> FileTypeProcessor | None:
        """Get processor for extension."""
        return self._processors.get(ext)

    def get_all_processors(self) -> list[FileTypeProcessor]:
        """Get list of unique processors."""
        seen: Set[int] = set()
        result: list[FileTypeProcessor] = []
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
