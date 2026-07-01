"""Project module file processors for editor file watching."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Set

from tcbase import log
from termin.editor_core.project_file_watcher import FilePreLoader


class ModuleFileProcessor(FilePreLoader):
    """Tracks Python module descriptor changes without reloading on file events."""

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
        return {".pymodule"}

    @property
    def resource_type(self) -> str:
        return "module"

    def on_file_added(self, path: str) -> None:
        self._mark_descriptor_changed(path)

    def on_file_changed(self, path: str) -> None:
        self._mark_descriptor_changed(path)

    def on_initial_file_added(self, path: str) -> None:
        self._file_to_resources.setdefault(path, set())

    def on_file_removed(self, path: str) -> None:
        self._mark_changed(path)

    def _mark_descriptor_changed(self, path: str) -> None:
        self._mark_changed(path)

    def _mark_changed(self, path: str) -> None:
        runtime = self._modules_runtime()
        module_ids = runtime.mark_modules_dirty_for_path(Path(path))
        if not module_ids:
            log.info(f"[ModuleFileProcessor] Module descriptor change is pending rescan: {path}")
            return
        for module_id in module_ids:
            log.info(f"[ModuleFileProcessor] Marked module '{module_id}' dirty after descriptor change: {path}")

    def _modules_runtime(self):
        if self._modules_runtime_provider is not None:
            return self._modules_runtime_provider()

        from termin.project_modules.runtime import get_project_modules_runtime

        return get_project_modules_runtime()


class ModuleInputFileProcessor(FilePreLoader):
    """Tracks native module input changes without choosing a reload policy."""

    _EXTENSIONS = {
        ".module",
        ".c",
        ".cc",
        ".cpp",
        ".cxx",
        ".h",
        ".hh",
        ".hpp",
        ".hxx",
        ".inl",
        ".ipp",
        ".ixx",
        ".cmake",
    }

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
        return set(self._EXTENSIONS)

    @property
    def resource_type(self) -> str:
        return "module_input"

    def on_file_added(self, path: str) -> None:
        self._mark_changed(path)

    def on_initial_file_added(self, path: str) -> None:
        self._file_to_resources.setdefault(path, set())

    def on_file_changed(self, path: str) -> None:
        self._mark_changed(path)

    def on_file_removed(self, path: str) -> None:
        self._mark_changed(path)
        self._file_to_resources.pop(path, None)

    def _mark_changed(self, path: str) -> None:
        runtime = self._modules_runtime()
        module_ids = runtime.mark_modules_dirty_for_path(path)
        if not module_ids:
            return

        for module_id in module_ids:
            log.info(f"[ModuleInputFileProcessor] Marked module '{module_id}' dirty after input change: {path}")
            self._file_to_resources.setdefault(path, set()).add(module_id)

    def _modules_runtime(self):
        if self._modules_runtime_provider is not None:
            return self._modules_runtime_provider()

        from termin.project_modules.runtime import get_project_modules_runtime

        return get_project_modules_runtime()
