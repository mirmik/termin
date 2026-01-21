"""
Module watcher for C++ hot-reload system.

Extends the project file watcher to track .cpp, .h files in modules
and trigger recompilation/reload when they change.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, Set

from termin._native import log

if TYPE_CHECKING:
    from PyQt6.QtCore import QFileSystemWatcher, QTimer
    from termin.entity._entity_native import ModuleLoader


@dataclass
class ModuleFileInfo:
    """Information about a watched module file."""

    module_name: str
    module_path: str  # Path to .module file
    file_path: str  # Path to .cpp/.h file


class ModuleWatcher:
    """
    Watches C++ module source files for changes and triggers hot-reload.

    This watcher monitors .cpp and .h files within modules defined by .module
    descriptor files. When source files change, it triggers recompilation
    and hot-reload of the affected module.
    """

    # Debounce delay for file changes (ms)
    DEBOUNCE_DELAY_MS = 500

    def __init__(
        self,
        on_module_changed: Callable[[str], None] | None = None,
        on_reload_complete: Callable[[str, bool, str], None] | None = None,
    ):
        """
        Initialize the module watcher.

        Args:
            on_module_changed: Callback when module files change (module_name)
            on_reload_complete: Callback when reload finishes (module_name, success, message)
        """
        self._file_watcher: "QFileSystemWatcher | None" = None
        self._debounce_timer: "QTimer | None" = None
        self._pending_modules: Set[str] = set()

        # module_name -> set of watched source files
        self._module_files: Dict[str, Set[str]] = {}

        # source_file -> module_name (reverse mapping)
        self._file_to_module: Dict[str, str] = {}

        # module_name -> module_path (.module file)
        self._module_paths: Dict[str, str] = {}

        # Watched directories
        self._watched_dirs: Set[str] = set()

        # Callbacks
        self._on_module_changed = on_module_changed
        self._on_reload_complete = on_reload_complete

        # Auto-reload flag
        self._auto_reload = True

    @property
    def auto_reload(self) -> bool:
        """Whether to automatically reload modules when source files change."""
        return self._auto_reload

    @auto_reload.setter
    def auto_reload(self, value: bool) -> None:
        self._auto_reload = value

    def enable(self) -> None:
        """Enable file watching."""
        if self._file_watcher is not None:
            return

        from PyQt6.QtCore import QFileSystemWatcher, QTimer

        self._file_watcher = QFileSystemWatcher()
        self._file_watcher.directoryChanged.connect(self._on_directory_changed)
        self._file_watcher.fileChanged.connect(self._on_file_changed)

        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._process_pending_changes)

    def disable(self) -> None:
        """Disable file watching and clear all state."""
        if self._debounce_timer is not None:
            self._debounce_timer.stop()
            self._debounce_timer = None

        if self._file_watcher is not None:
            self._file_watcher.directoryChanged.disconnect(self._on_directory_changed)
            self._file_watcher.fileChanged.disconnect(self._on_file_changed)
            self._file_watcher = None

        self._module_files.clear()
        self._file_to_module.clear()
        self._module_paths.clear()
        self._watched_dirs.clear()
        self._pending_modules.clear()

    def watch_module(self, module_path: str) -> bool:
        """
        Start watching a module's source files.

        Args:
            module_path: Path to the .module descriptor file

        Returns:
            True if module was added successfully
        """
        if self._file_watcher is None:
            log.warning("[ModuleWatcher] File watcher not enabled")
            return False

        if not os.path.exists(module_path):
            log.error(f"[ModuleWatcher] Module file not found: {module_path}")
            return False

        # Parse module descriptor
        module_info = self._parse_module_file(module_path)
        if module_info is None:
            return False

        module_name = module_info["name"]
        module_dir = os.path.dirname(module_path)

        # Already watching
        if module_name in self._module_files:
            return True

        self._module_files[module_name] = set()
        self._module_paths[module_name] = module_path

        # Watch .module file itself
        self._file_watcher.addPath(module_path)
        self._file_to_module[module_path] = module_name
        self._module_files[module_name].add(module_path)

        # Find and watch source files
        for pattern in module_info.get("sources", []):
            self._watch_source_pattern(module_name, module_dir, pattern)

        log.info(
            f"[ModuleWatcher] Watching module '{module_name}' with {len(self._module_files[module_name])} files"
        )
        return True

    def unwatch_module(self, module_name: str) -> None:
        """Stop watching a module."""
        if module_name not in self._module_files:
            return

        if self._file_watcher is not None:
            for file_path in self._module_files[module_name]:
                if file_path in self._file_watcher.files():
                    self._file_watcher.removePath(file_path)
                if file_path in self._file_to_module:
                    del self._file_to_module[file_path]

        del self._module_files[module_name]
        if module_name in self._module_paths:
            del self._module_paths[module_name]

        log.info(f"[ModuleWatcher] Stopped watching module '{module_name}'")

    def get_watched_modules(self) -> list[str]:
        """Get list of watched module names."""
        return list(self._module_files.keys())

    def get_module_files(self, module_name: str) -> list[str]:
        """Get list of watched files for a module."""
        return list(self._module_files.get(module_name, []))

    def trigger_reload(self, module_name: str) -> bool:
        """
        Manually trigger a module reload.

        Args:
            module_name: Name of module to reload

        Returns:
            True if reload was triggered successfully
        """
        from termin.entity._entity_native import ModuleLoader

        loader = ModuleLoader.instance()

        if not loader.is_loaded(module_name):
            log.error(f"[ModuleWatcher] Module not loaded: {module_name}")
            if self._on_reload_complete:
                self._on_reload_complete(module_name, False, "Module not loaded")
            return False

        success = loader.reload_module(module_name)

        if self._on_reload_complete:
            message = "" if success else loader.last_error
            self._on_reload_complete(module_name, success, message)

        return success

    def _parse_module_file(self, path: str) -> dict | None:
        """Parse a .module JSON file."""
        import json

        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error(f"[ModuleWatcher] Failed to parse module file: {e}")
            return None

    def _watch_source_pattern(
        self, module_name: str, base_dir: str, pattern: str
    ) -> None:
        """Watch source files matching a glob pattern."""
        if self._file_watcher is None:
            return

        # Handle glob patterns
        if "*" in pattern:
            import glob

            full_pattern = os.path.join(base_dir, pattern)
            for file_path in glob.glob(full_pattern, recursive=True):
                self._add_source_file(module_name, file_path)
        else:
            file_path = os.path.join(base_dir, pattern)
            if os.path.exists(file_path):
                self._add_source_file(module_name, file_path)

        # Watch parent directories for new files
        pattern_dir = os.path.dirname(os.path.join(base_dir, pattern))
        if os.path.isdir(pattern_dir) and pattern_dir not in self._watched_dirs:
            self._file_watcher.addPath(pattern_dir)
            self._watched_dirs.add(pattern_dir)

    def _add_source_file(self, module_name: str, file_path: str) -> None:
        """Add a source file to watching."""
        if self._file_watcher is None:
            return

        file_path = os.path.normpath(file_path)

        if file_path not in self._file_to_module:
            self._file_watcher.addPath(file_path)
            self._file_to_module[file_path] = module_name
            self._module_files[module_name].add(file_path)

    def _on_directory_changed(self, path: str) -> None:
        """Handle directory changes (new files)."""
        if self._file_watcher is None:
            return

        # Find which module this directory belongs to
        for module_name, module_path in self._module_paths.items():
            module_dir = os.path.dirname(module_path)
            if path.startswith(module_dir):
                # Re-scan for new source files
                module_info = self._parse_module_file(module_path)
                if module_info:
                    for pattern in module_info.get("sources", []):
                        self._watch_source_pattern(module_name, module_dir, pattern)
                break

    def _on_file_changed(self, path: str) -> None:
        """Handle file modification with debouncing."""
        # Re-add path if removed (Linux quirk)
        if self._file_watcher is not None and os.path.exists(path):
            if path not in self._file_watcher.files():
                self._file_watcher.addPath(path)

        path = os.path.normpath(path)
        module_name = self._file_to_module.get(path)

        if module_name is None:
            return

        self._pending_modules.add(module_name)

        if self._on_module_changed:
            self._on_module_changed(module_name)

        if self._debounce_timer is not None:
            self._debounce_timer.start(self.DEBOUNCE_DELAY_MS)

    def _process_pending_changes(self) -> None:
        """Process pending module changes after debounce delay."""
        if not self._auto_reload:
            self._pending_modules.clear()
            return

        pending = self._pending_modules.copy()
        self._pending_modules.clear()

        for module_name in pending:
            self.trigger_reload(module_name)


# Singleton instance
_instance: ModuleWatcher | None = None


def get_module_watcher() -> ModuleWatcher:
    """Get the global module watcher instance."""
    global _instance
    if _instance is None:
        _instance = ModuleWatcher()
    return _instance
