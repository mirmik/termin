"""Watcher policy for Python source owned by project modules."""

from __future__ import annotations

from collections.abc import Callable
from typing import Set

from tcbase import log
from termin.editor_core.project_file_watcher import FilePreLoader


class ComponentFileProcessor(FilePreLoader):
    """Marks the owning ``.pymodule`` dirty when one of its Python files changes.

    Standalone Python files are intentionally inert.  Python code enters the
    component registries only while an explicit project module is being loaded,
    so the module runtime remains the sole owner of import and unload lifecycle.
    """

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
        return "module_input"

    def on_file_added(self, path: str) -> None:
        self._mark_owning_modules_dirty(path)

    def on_initial_file_added(self, path: str) -> None:
        # Discovery/load of declared modules is performed by ProjectModulesRuntime.
        # Merely finding a Python file must never execute it or dirty a module.
        self._file_to_resources.setdefault(path, set())

    def on_file_changed(self, path: str) -> None:
        self._mark_owning_modules_dirty(path)

    def on_file_removed(self, path: str) -> None:
        self._mark_owning_modules_dirty(path)
        self._file_to_resources.pop(path, None)

    def _mark_owning_modules_dirty(self, path: str) -> None:
        runtime = self._modules_runtime()
        module_ids = runtime.mark_modules_dirty_for_path(path)
        if not module_ids:
            log.debug(f"[ComponentProcessor] Python file has no module owner and remains inert: {path}")
            return

        tracked = self._file_to_resources.setdefault(path, set())
        for module_id in module_ids:
            tracked.add(module_id)
            log.info(f"[ComponentProcessor] Marked Python module '{module_id}' dirty after source change: {path}")

    def _modules_runtime(self):
        if self._modules_runtime_provider is not None:
            return self._modules_runtime_provider()

        from termin.project_modules.runtime import get_project_modules_runtime

        return get_project_modules_runtime()
