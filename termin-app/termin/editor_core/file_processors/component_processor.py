"""Component file processor for Python files containing Component subclasses."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Set

from tcbase import log
from termin.editor_core.project_file_watcher import FilePreLoader


LOOSE_PYTHON_NAMESPACE = "termin_project"


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
        self._dirty_loose_paths: set[str] = set()

    @property
    def extensions(self) -> Set[str]:
        return {".py"}

    @property
    def resource_type(self) -> str:
        return "component"

    def on_file_added(self, path: str) -> None:
        """Mark a new Python file dirty for explicit reload."""
        # Skip private files
        filename = os.path.basename(path)
        if filename.startswith("_"):
            return

        # Skip files inside packages (they should be imported via .pymodule)
        if _is_inside_package(path):
            self._mark_owning_modules_dirty(path)
            return

        self._mark_loose_component_dirty(path)

    def on_initial_file_added(self, path: str) -> None:
        """Load loose components during project scan without dirtying them."""
        filename = os.path.basename(path)
        if filename.startswith("_"):
            return

        if _is_inside_package(path):
            return

        self._load_loose_component_file(path)

    def on_file_changed(self, path: str) -> None:
        """Mark a modified Python file dirty for explicit reload."""
        filename = os.path.basename(path)
        if filename.startswith("_"):
            return

        # Skip files inside packages (they should be imported via .pymodule)
        if _is_inside_package(path):
            self._mark_owning_modules_dirty(path)
            return

        self._mark_loose_component_dirty(path)

    def on_file_removed(self, path: str) -> None:
        """Handle Python file deletion."""
        self._dirty_loose_paths.discard(path)
        if path in self._file_to_resources:
            del self._file_to_resources[path]

    def dirty_component_paths(self) -> tuple[str, ...]:
        return tuple(sorted(self._dirty_loose_paths))

    def reload_dirty_components(self) -> bool:
        dirty_paths = list(self.dirty_component_paths())
        if not dirty_paths:
            return True

        success = True
        for path in dirty_paths:
            if not os.path.exists(path):
                self._dirty_loose_paths.discard(path)
                continue
            if not self._reload_loose_component_file(path):
                success = False
                break
            self._dirty_loose_paths.discard(path)
        return success

    def _load_loose_component_file(self, path: str) -> bool:
        try:
            loaded = self._scan_loose_components(path)

            if loaded:
                if path not in self._file_to_resources:
                    self._file_to_resources[path] = set()
                self._file_to_resources[path].update(loaded)

                for name in loaded:
                    self._notify_reloaded(name)
            return True

        except Exception:
            log.error(f"[ComponentProcessor] Failed to load {path}", exc_info=True)
            return False

    def _reload_loose_component_file(self, path: str) -> bool:
        try:
            # Reload the file
            loaded = self._scan_loose_components(path)

            # Update tracking
            if path not in self._file_to_resources:
                self._file_to_resources[path] = set()
            self._file_to_resources[path].update(loaded)

            # Notify about reloaded components
            for name in loaded:
                self._notify_reloaded(name)
            if not loaded:
                self._reload_tracked_loose_components(trigger_path=path)
            return True

        except Exception:
            log.error(f"[ComponentProcessor] Failed to reload {path}", exc_info=True)
            return False

    def _mark_loose_component_dirty(self, path: str) -> None:
        self._dirty_loose_paths.add(path)
        log.info(f"[ComponentProcessor] Marked loose Python file dirty: {path}")

    def _mark_owning_modules_dirty(self, path: str) -> None:
        runtime = self._modules_runtime()
        module_ids = runtime.mark_modules_dirty_for_path(path)
        for module_id in module_ids:
            log.info(f"[ComponentProcessor] Marked Python module '{module_id}' dirty after package file change: {path}")

    def _modules_runtime(self):
        if self._modules_runtime_provider is not None:
            return self._modules_runtime_provider()

        from termin.project_modules.runtime import get_project_modules_runtime

        return get_project_modules_runtime()

    def _reload_tracked_loose_components(self, *, trigger_path: str) -> None:
        """Conservatively refresh loose components after helper-only changes."""
        for component_path in sorted(self._file_to_resources):
            if component_path == trigger_path or not os.path.exists(component_path):
                continue
            try:
                loaded = self._scan_loose_components(component_path)
            except Exception:
                log.error(
                    f"[ComponentProcessor] Failed to reload dependent loose component {component_path}",
                    exc_info=True,
                )
                continue

            self._file_to_resources[component_path].update(loaded)
            for name in loaded:
                self._notify_reloaded(name)

    def _scan_loose_components(self, path: str) -> list[str]:
        return self._resource_manager.scan_components(
            [path],
            project_root=self._project_root,
            namespace=LOOSE_PYTHON_NAMESPACE if self._project_root is not None else None,
        )
