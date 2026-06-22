"""Component file processor for Python files containing Component subclasses."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Set

from tcbase import log
from termin.assets.project_file_watcher import FilePreLoader


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


class ComponentFileProcessor(FilePreLoader):
    """Handles .py files containing Component subclasses."""

    def __init__(
        self,
        resource_manager: object,
        on_resource_reloaded: Callable[[str, str], None] | None = None,
        modules_runtime_provider: Callable[[], object] | None = None,
    ) -> None:
        super().__init__(resource_manager, on_resource_reloaded=on_resource_reloaded)
        self._modules_runtime_provider = modules_runtime_provider

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
            self._reload_owning_modules(path)
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
            self._reload_owning_modules(path)
            return

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

    def _reload_owning_modules(self, path: str) -> None:
        runtime = self._modules_runtime()
        if not runtime.auto_reload_enabled:
            return

        module_ids = runtime.reload_modules_for_path(path)
        for module_id in module_ids:
            log.info(f"[ComponentProcessor] Reloaded Python module {module_id} after package file change")

    def _modules_runtime(self):
        if self._modules_runtime_provider is not None:
            return self._modules_runtime_provider()

        from termin.modules import get_project_modules_runtime

        return get_project_modules_runtime()
