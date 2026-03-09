from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from tcbase import log
from termin import _native
from termin_modules import (
    CppModuleBackend,
    ModuleEnvironment,
    ModuleEvent,
    ModuleRecord,
    ModuleRuntime,
    PythonModuleBackend,
)

TermModulesIntegration = _native.modules.TermModulesIntegration


class ProjectModulesRuntime:
    def __init__(self) -> None:
        self._project_root: Path | None = None
        self._integration = TermModulesIntegration()
        self._runtime = ModuleRuntime()
        self._listeners: list[Callable[[ModuleEvent], None]] = []
        self._configure_environment()
        self._configure_runtime()

    @property
    def project_root(self) -> Path | None:
        return self._project_root

    @property
    def last_error(self) -> str:
        return self._runtime.last_error

    def runtime(self) -> ModuleRuntime:
        return self._runtime

    def records(self) -> list[ModuleRecord]:
        return list(self._runtime.list())

    def find(self, module_id: str) -> ModuleRecord | None:
        return self._runtime.find(module_id)

    def add_listener(self, listener: Callable[[ModuleEvent], None]) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[ModuleEvent], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def load_project(self, project_root: str | Path | None = None) -> bool:
        if project_root is not None:
            self._project_root = Path(project_root).resolve()

        if self._project_root is None:
            log.error("[ProjectModulesRuntime] project root is not set")
            return False

        self._shutdown_runtime()
        self._recreate_runtime()
        self._runtime.discover(self._project_root)
        if self._runtime.last_error:
            log.error(f"[ProjectModulesRuntime] discover failed: {self._runtime.last_error}")
        return self._runtime.load_all()

    def discover_project(self, project_root: str | Path | None = None) -> bool:
        if project_root is not None:
            self._project_root = Path(project_root).resolve()

        if self._project_root is None:
            log.error("[ProjectModulesRuntime] project root is not set")
            return False

        self._shutdown_runtime()
        self._recreate_runtime()
        self._runtime.discover(self._project_root)
        return not self._runtime.last_error

    def reload_module(self, module_id: str) -> bool:
        return self._runtime.reload_module(module_id)

    def unload_module(self, module_id: str) -> bool:
        return self._runtime.unload_module(module_id)

    def load_module(self, module_id: str) -> bool:
        return self._runtime.load_module(module_id)

    def load_descriptor(self, descriptor_path: str | Path) -> bool:
        descriptor = Path(descriptor_path).resolve()

        if self._project_root is None:
            self._project_root = descriptor.parent

        self._runtime.discover(self._project_root)
        record = self.find_by_descriptor(descriptor)
        if record is None:
            log.error(f"[ProjectModulesRuntime] descriptor is not part of discovered project: {descriptor}")
            return False
        return self._runtime.load_module(record.id)

    def find_by_descriptor(self, descriptor_path: str | Path) -> ModuleRecord | None:
        target = Path(descriptor_path).resolve()
        for record in self.records():
            if Path(record.descriptor_path).resolve() == target:
                return record
        return None

    def _dispatch_event(self, event: ModuleEvent) -> None:
        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception as e:
                log.error(f"[ProjectModulesRuntime] event listener failed: {e}")

    def _configure_environment(self) -> None:
        environment = ModuleEnvironment()
        environment.python_executable = sys.executable

        import termin

        termin_path = Path(termin.__file__).resolve().parent
        install_root = termin_path.parent.parent.parent
        default_root = Path("/opt/termin")
        prefix_root = install_root
        if not (prefix_root / "lib").exists() and default_root.exists():
            prefix_root = default_root

        environment.sdk_prefix = str(prefix_root)
        environment.cmake_prefix_path = str(prefix_root)
        environment.lib_dir = str(prefix_root / "lib")

        self._integration.set_environment(environment)

    def _configure_runtime(self) -> None:
        self._runtime.register_cpp_backend(CppModuleBackend())
        self._runtime.register_python_backend(PythonModuleBackend())
        self._integration.configure_runtime(self._runtime)
        self._runtime.set_event_callback(self._dispatch_event)

    def _recreate_runtime(self) -> None:
        self._runtime = ModuleRuntime()
        self._configure_runtime()

    def _shutdown_runtime(self) -> None:
        records_by_id: dict[str, ModuleRecord] = {}
        for record in self.records():
            records_by_id[record.id] = record

        unloaded: set[str] = set()

        def unload_recursive(module_id: str) -> None:
            if module_id in unloaded:
                return

            for record in list(records_by_id.values()):
                if module_id in record.dependencies:
                    unload_recursive(record.id)

            record = records_by_id.get(module_id)
            if record is None:
                unloaded.add(module_id)
                return

            if record.state.name == "Loaded":
                if not self._runtime.unload_module(module_id):
                    log.error(
                        f"[ProjectModulesRuntime] failed to unload module '{module_id}': {self._runtime.last_error}"
                    )
            unloaded.add(module_id)

        for record in list(records_by_id.values()):
            unload_recursive(record.id)


_instance: ProjectModulesRuntime | None = None


def get_project_modules_runtime() -> ProjectModulesRuntime:
    global _instance
    if _instance is None:
        _instance = ProjectModulesRuntime()
    return _instance
