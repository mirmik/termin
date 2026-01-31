"""Component file processor for Python files containing Component subclasses."""

from __future__ import annotations

import os
from typing import Set

from termin._native import log
from termin.editor.project_file_watcher import FileTypeProcessor


def _is_inside_package(path: str) -> bool:
    """Check if file is inside a Python package (directory with __init__.py).

    Files inside packages should be imported via the package, not loaded individually.
    """
    directory = os.path.dirname(path)
    while directory:
        init_file = os.path.join(directory, "__init__.py")
        if os.path.exists(init_file):
            return True
        parent = os.path.dirname(directory)
        if parent == directory:
            break
        directory = parent
    return False


class ComponentFileProcessor(FileTypeProcessor):
    """Handles .py files containing Component subclasses."""

    @property
    def extensions(self) -> Set[str]:
        return {".py"}

    @property
    def resource_type(self) -> str:
        return "component"

    def on_file_added(self, path: str) -> None:
        """Load components from new Python file."""
        # Skip private files
        filename = os.path.basename(path)
        if filename.startswith("_"):
            return

        # Skip files inside packages (they should be imported via .pymodule)
        if _is_inside_package(path):
            return

        try:
            loaded = self._resource_manager.scan_components([path])

            if loaded:
                if path not in self._file_to_resources:
                    self._file_to_resources[path] = set()
                self._file_to_resources[path].update(loaded)

                for name in loaded:
                    self._notify_reloaded(name)

        except Exception:
            log.error(f"[ComponentProcessor] Failed to load {path}", exc_info=True)

    def on_file_changed(self, path: str) -> None:
        """Reload components from modified Python file."""
        filename = os.path.basename(path)
        if filename.startswith("_"):
            return

        # Skip files inside packages (they should be imported via .pymodule)
        if _is_inside_package(path):
            return

        # Get previously loaded components from this file
        old_components = self._file_to_resources.get(path, set()).copy()

        try:
            # Reload the file
            loaded = self._resource_manager.scan_components([path])

            # Update tracking
            if path not in self._file_to_resources:
                self._file_to_resources[path] = set()
            self._file_to_resources[path].update(loaded)

            # Notify about reloaded components
            for name in loaded:
                self._notify_reloaded(name)

        except Exception:
            log.error(f"[ComponentProcessor] Failed to reload {path}", exc_info=True)

    def on_file_removed(self, path: str) -> None:
        """Handle Python file deletion."""
        if path in self._file_to_resources:
            del self._file_to_resources[path]
