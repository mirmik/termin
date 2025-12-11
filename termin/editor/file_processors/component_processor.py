"""Component file processor for Python files containing Component subclasses."""

from __future__ import annotations

import os
from typing import Set

from termin.editor.project_file_watcher import FileTypeProcessor


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

        try:
            loaded = self._resource_manager.scan_components([path])

            if loaded:
                if path not in self._file_to_resources:
                    self._file_to_resources[path] = set()
                self._file_to_resources[path].update(loaded)

                for name in loaded:
                    print(f"[ComponentProcessor] Loaded: {name}")
                    self._notify_reloaded(name)

        except Exception as e:
            print(f"[ComponentProcessor] Failed to load {path}: {e}")

    def on_file_changed(self, path: str) -> None:
        """Reload components from modified Python file."""
        filename = os.path.basename(path)
        if filename.startswith("_"):
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
                print(f"[ComponentProcessor] Reloaded: {name}")
                self._notify_reloaded(name)

        except Exception as e:
            print(f"[ComponentProcessor] Failed to reload {path}: {e}")

    def on_file_removed(self, path: str) -> None:
        """Handle Python file deletion."""
        if path in self._file_to_resources:
            del self._file_to_resources[path]
