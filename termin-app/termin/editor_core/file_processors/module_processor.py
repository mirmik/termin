"""Project module file processors for editor file watching."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Set

from tcbase import log
from termin.assets.project_file_watcher import FilePreLoader


class ModuleFileProcessor(FilePreLoader):
    """Handles Python module descriptor changes through ProjectModulesRuntime."""

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
        self._load_or_reload_descriptor(path)

    def on_file_changed(self, path: str) -> None:
        self._load_or_reload_descriptor(path)

    def on_file_removed(self, path: str) -> None:
        runtime = self._modules_runtime()
        if not runtime.auto_reload_enabled:
            return

        record = runtime.find_by_descriptor(path)
        if record is None:
            return
        if not runtime.unload_module(record.id):
            log.error(f"[ModuleFileProcessor] Failed to unload removed module {record.id}: {runtime.last_error}")
            return
        self._notify_reloaded(record.id)

    def _load_or_reload_descriptor(self, path: str) -> None:
        runtime = self._modules_runtime()
        if not runtime.auto_reload_enabled:
            return

        module_id = runtime.reload_descriptor(Path(path))
        if module_id is None:
            log.error(f"[ModuleFileProcessor] Failed to load or reload module descriptor {path}: {runtime.last_error}")
            return
        self._notify_reloaded(module_id)

    def _modules_runtime(self):
        if self._modules_runtime_provider is not None:
            return self._modules_runtime_provider()

        from termin.modules.runtime import get_project_modules_runtime

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

        from termin.modules.runtime import get_project_modules_runtime

        return get_project_modules_runtime()
