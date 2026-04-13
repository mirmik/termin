from __future__ import annotations

import os
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
        self._build_output_listeners: list[Callable[[str, str], None]] = []
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

    def add_build_output_listener(self, listener: Callable[[str, str], None]) -> None:
        if listener not in self._build_output_listeners:
            self._build_output_listeners.append(listener)

    def remove_build_output_listener(self, listener: Callable[[str, str], None]) -> None:
        if listener in self._build_output_listeners:
            self._build_output_listeners.remove(listener)

    def load_project(self, project_root: str | Path | None = None) -> bool:
        if project_root is not None:
            self._project_root = Path(project_root).resolve()

        if self._project_root is None:
            log.error("[ProjectModulesRuntime] project root is not set")
            return False

        self._update_environment()
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

        self._update_environment()
        self._shutdown_runtime()
        self._recreate_runtime()
        self._runtime.discover(self._project_root)
        return not self._runtime.last_error

    def reload_module(self, module_id: str) -> bool:
        return self._runtime.reload_module(module_id)

    def needs_rebuild(self, module_id: str) -> bool:
        return self._runtime.needs_rebuild(module_id)

    def stale_modules(self) -> list[str]:
        """Return list of module IDs that need rebuild."""
        result = []
        for record in self.records():
            if self._runtime.needs_rebuild(record.id):
                result.append(record.id)
        return result

    def rebuild_stale_modules(self) -> bool:
        """Rebuild all modules that need it. Returns True if all succeeded."""
        stale = self.stale_modules()
        if not stale:
            return True
        success = True
        for module_id in stale:
            log.info(f"[ProjectModulesRuntime] Rebuilding stale module: {module_id}")
            if not self._runtime.reload_module(module_id):
                log.error(f"[ProjectModulesRuntime] Failed to rebuild: {module_id}: {self._runtime.last_error}")
                success = False
        return success

    def build_module(self, module_id: str) -> bool:
        return self._runtime.build_module(module_id)

    def clean_module(self, module_id: str) -> bool:
        return self._runtime.clean_module(module_id)

    def rebuild_module(self, module_id: str) -> bool:
        return self._runtime.rebuild_module(module_id)

    def unload_module(self, module_id: str) -> bool:
        return self._runtime.unload_module(module_id)

    def load_module(self, module_id: str) -> bool:
        return self._runtime.load_module(module_id)

    def load_descriptor(self, descriptor_path: str | Path) -> bool:
        descriptor = Path(descriptor_path).resolve()

        if self._project_root is None:
            self._project_root = descriptor.parent

        self._update_environment()
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

        # termin is a namespace package → __file__ is None; use __path__[0].
        # The first entry points at site-packages/termin; walk up three levels
        # to reach the install prefix (same semantics as the previous
        # Path(termin.__file__).resolve().parent.parent.parent.parent chain
        # in the legacy layout where termin/__init__.py existed).
        termin_path = Path(termin.__path__[0]).resolve()
        prefix_root = termin_path.parent.parent.parent
        sdk_env = os.environ.get("TERMIN_SDK")
        if sdk_env:
            prefix_root = Path(sdk_env)

        environment.sdk_prefix = str(prefix_root)
        environment.cmake_prefix_path = str(prefix_root)
        environment.lib_dir = str(prefix_root / "lib")
        environment.allow_python_package_install = True
        environment.use_project_venv = False
        self._integration.set_environment(environment)
        self._runtime.set_environment(environment)

    def _update_environment(self) -> None:
        environment = self._integration.environment
        if self._project_root is None:
            environment.project_root = ""
            environment.project_venv_path = ""
            environment.use_project_venv = False
        else:
            environment.project_root = str(self._project_root)
            environment.project_venv_path = str(self._project_root / ".venv")
            environment.use_project_venv = True

        self._integration.set_environment(environment)
        self._runtime.set_environment(environment)

    def _configure_runtime(self) -> None:
        self._runtime.register_cpp_backend(CppModuleBackend())
        self._runtime.register_python_backend(PythonModuleBackend())
        self._integration.configure_runtime(self._runtime)
        self._runtime.set_event_callback(self._dispatch_event)
        self._runtime.set_build_output_callback(self._on_build_output)

    def _on_build_output(self, module_id: str, line: str) -> None:
        log.info(f"[{module_id}] {line}")
        for listener in list(self._build_output_listeners):
            try:
                listener(module_id, line)
            except Exception as e:
                log.error(f"[ProjectModulesRuntime] build output listener failed: {e}")

    def _recreate_runtime(self) -> None:
        self._runtime = ModuleRuntime()
        self._runtime.set_environment(self._integration.environment)
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


def upgrade_scene_unknown_components(scene) -> int:
    if scene is None:
        return 0

    from termin.scene import upgrade_unknown_components

    stats = upgrade_unknown_components(scene)
    if stats.failed > 0:
        log.error(
            f"[ProjectModulesRuntime] failed to upgrade {stats.failed} unknown components"
        )
    return int(stats.upgraded)
