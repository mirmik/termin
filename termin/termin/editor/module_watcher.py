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

from tcbase import log

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
        get_scene: Callable[[], object] | None = None,
    ):
        """
        Initialize the module watcher.

        Args:
            on_module_changed: Callback when module files change (module_name)
            on_reload_complete: Callback when reload finishes (module_name, success, message)
            get_scene: Callback to get current scene for upgrading unknown components
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
        self._get_scene = get_scene
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

    def set_scene_getter(self, get_scene: Callable[[], object] | None) -> None:
        """Set the callback to get the current scene."""
        self._get_scene = get_scene

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

        # Watch all C++ source files in the module directory
        self._watch_cpp_sources(module_name, module_dir)

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

    def get_watched_modules(self) -> list[str]:
        """Get list of watched module names."""
        return list(self._module_files.keys())

    def get_module_files(self, module_name: str) -> list[str]:
        """Get list of watched files for a module."""
        return list(self._module_files.get(module_name, []))

    def get_module_path(self, module_name: str) -> str | None:
        """Get path to .module file for a module."""
        return self._module_paths.get(module_name)

    def trigger_reload(self, module_name: str) -> bool:
        """
        Manually trigger a module reload (or initial load if not yet loaded).

        Args:
            module_name: Name of module to reload

        Returns:
            True if reload was triggered successfully
        """
        from termin.entity._entity_native import ModuleLoader

        loader = ModuleLoader.instance()

        if not loader.is_loaded(module_name):
            # Module not loaded yet - try initial load
            module_path = self._module_paths.get(module_name)
            if not module_path:
                log.error(f"[ModuleWatcher] Module path not found: {module_name}")
                if self._on_reload_complete:
                    self._on_reload_complete(module_name, False, "Module path not found")
                return False

            success = loader.load_module(module_path)
        else:
            success = loader.reload_module(module_name)

        if success:
            # Try to upgrade any UnknownComponents that can now be resolved
            self._try_upgrade_unknown_components()

        if self._on_reload_complete:
            message = "" if success else loader.last_error
            self._on_reload_complete(module_name, success, message)

        return success

    def _try_upgrade_unknown_components(self) -> None:
        """Try to upgrade UnknownComponents after module reload."""
        try:
            from termin.entity.unknown_component import upgrade_unknown_components

            scene = self._get_scene() if self._get_scene else None
            if scene:
                upgrade_unknown_components(scene)
        except Exception as e:
            log.error(f"[ModuleWatcher] Failed to upgrade components: {e}")

    def _parse_module_file(self, path: str) -> dict | None:
        """Parse a .module JSON file."""
        import json

        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error(f"[ModuleWatcher] Failed to parse module file: {e}")
            return None

    def _watch_cpp_sources(self, module_name: str, module_dir: str) -> None:
        """Watch all C++ source files in the module directory."""
        if self._file_watcher is None:
            return

        cpp_extensions = {".cpp", ".c", ".cc", ".cxx", ".h", ".hpp", ".hxx"}

        for root, dirs, files in os.walk(module_dir):
            # Skip build directories
            dirs[:] = [d for d in dirs if d not in ("build", ".git", "__pycache__")]

            # Watch the directory for new files
            if root not in self._watched_dirs:
                self._file_watcher.addPath(root)
                self._watched_dirs.add(root)

            # Watch source files
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in cpp_extensions:
                    file_path = os.path.join(root, f)
                    self._add_source_file(module_name, file_path)

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
                # Re-scan for new source files in the changed directory
                self._watch_cpp_sources(module_name, path)
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
