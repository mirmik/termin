from __future__ import annotations

import atexit
import os
import sys
import weakref
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from tcbase import log
from termin.engine import TermModulesIntegration
from termin_modules import (
    CppModuleBackend,
    ModuleEnvironment,
    ModuleEvent,
    ModuleKind,
    ModuleRecord,
    ModuleRuntime,
    PythonModuleBackend,
)


@dataclass(frozen=True)
class ModuleFileChange:
    module_id: str
    kind: str
    path: Path
    reason: str


def _is_python_executable(path: Path) -> bool:
    name = path.name.lower()
    return name in {"python", "python3", "python.exe", "pythonw.exe"} or name.startswith("python3.")


def _sdk_python_executable(prefix_root: Path) -> Path | None:
    if sys.platform == "win32":
        candidates = (
            prefix_root / "python" / "python.exe",
            prefix_root / "bin" / "python.exe",
        )
    else:
        candidates = (
            prefix_root / "bin" / "python3",
            prefix_root / "bin" / "python",
        )

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


class ProjectModulesRuntime:
    def __init__(self) -> None:
        self._project_root: Path | None = None
        self._integration = TermModulesIntegration()
        self._runtime = ModuleRuntime()
        self._auto_reload_enabled = False
        self._listeners: list[Callable[[ModuleEvent], None]] = []
        self._build_output_listeners: list[Callable[[str, str], None]] = []
        self._dirty_module_reasons: dict[str, set[str]] = {}
        self._closed = False
        self._configure_environment()
        self._configure_runtime()

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def project_root(self) -> Path | None:
        return self._project_root

    @property
    def last_error(self) -> str:
        return self._runtime.last_error

    @property
    def auto_reload_enabled(self) -> bool:
        return self._auto_reload_enabled

    @auto_reload_enabled.setter
    def auto_reload_enabled(self, enabled: bool) -> None:
        self._auto_reload_enabled = bool(enabled)

    @property
    def sync_live_scenes(self) -> bool:
        return bool(self._integration.environment.sync_live_scenes)

    def set_sync_live_scenes(self, enabled: bool) -> None:
        environment = self._integration.environment
        environment.sync_live_scenes = bool(enabled)
        self._integration.set_environment(environment)
        self._runtime.set_environment(environment)

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
        self._ensure_open()
        if project_root is not None:
            self._project_root = Path(project_root).resolve()

        if self._project_root is None:
            log.error("[ProjectModulesRuntime] project root is not set")
            return False

        self._update_environment()
        self._shutdown_runtime()
        self._recreate_runtime()
        self._configure_discovery_ignored_roots()
        self._runtime.discover(self._project_root)
        if self._runtime.last_error:
            log.error(f"[ProjectModulesRuntime] discover failed: {self._runtime.last_error}")
        success = self._runtime.load_all()
        if success:
            self._dirty_module_reasons.clear()
        return success

    def discover_project(self, project_root: str | Path | None = None) -> bool:
        self._ensure_open()
        if project_root is not None:
            self._project_root = Path(project_root).resolve()

        if self._project_root is None:
            log.error("[ProjectModulesRuntime] project root is not set")
            return False

        self._update_environment()
        self._shutdown_runtime()
        self._recreate_runtime()
        self._configure_discovery_ignored_roots()
        self._runtime.discover(self._project_root)
        return not self._runtime.last_error

    def reload_module(self, module_id: str) -> bool:
        self._ensure_open()
        success = self._runtime.reload_module_with_dependents(module_id)
        if success:
            self._dirty_module_reasons.pop(module_id, None)
        return success

    def reload_descriptor(self, descriptor_path: str | Path) -> str | None:
        descriptor = Path(descriptor_path).resolve()
        record = self.find_by_descriptor(descriptor)
        if record is None:
            if not self.load_descriptor(descriptor):
                return None
            record = self.find_by_descriptor(descriptor)
            return None if record is None else record.id

        if not self.reload_module(record.id):
            return None
        self._dirty_module_reasons.pop(record.id, None)
        return record.id

    def reload_modules_for_path(self, path: str | Path) -> list[str]:
        target = Path(path).resolve()
        module_ids = self.module_ids_for_path(target)
        reloaded: list[str] = []
        for module_id in module_ids:
            if self.reload_module(module_id):
                reloaded.append(module_id)
            else:
                log.error(
                    f"[ProjectModulesRuntime] failed to reload module '{module_id}' for changed path {target}: "
                    f"{self.last_error}"
                )
        return reloaded

    def module_ids_for_path(self, path: str | Path) -> list[str]:
        return [
            change.module_id
            for change in self.module_file_changes_for_path(path)
            if change.kind == "python_package"
        ]

    def module_file_changes_for_path(self, path: str | Path) -> list[ModuleFileChange]:
        target = Path(path).resolve()
        result: list[ModuleFileChange] = []
        for record in self.records():
            descriptor = Path(record.descriptor_path).resolve()
            if target == descriptor:
                if record.kind == ModuleKind.Cpp:
                    result.append(ModuleFileChange(record.id, "cpp_descriptor", target, "descriptor"))
                else:
                    result.append(ModuleFileChange(record.id, "python_descriptor", target, "descriptor"))
                continue

            if record.kind == ModuleKind.Python:
                if self._python_record_owns_path(record, target):
                    result.append(ModuleFileChange(record.id, "python_package", target, "package_file"))
                continue

            if record.kind == ModuleKind.Cpp and self._cpp_record_owns_path(record, target):
                result.append(ModuleFileChange(record.id, "cpp_input", target, "module_directory_input"))
        return result

    def mark_modules_dirty_for_path(self, path: str | Path) -> list[str]:
        module_ids: list[str] = []
        for change in self.module_file_changes_for_path(path):
            if change.kind not in {"cpp_descriptor", "cpp_input"}:
                continue
            reasons = self._dirty_module_reasons.setdefault(change.module_id, set())
            reasons.add(f"{change.reason}: {change.path}")
            if change.module_id not in module_ids:
                module_ids.append(change.module_id)
        return module_ids

    def dirty_modules(self) -> dict[str, tuple[str, ...]]:
        return {
            module_id: tuple(sorted(reasons))
            for module_id, reasons in sorted(self._dirty_module_reasons.items())
        }

    def clear_dirty_module(self, module_id: str) -> None:
        self._dirty_module_reasons.pop(module_id, None)

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
            if not self.reload_module(module_id):
                log.error(f"[ProjectModulesRuntime] Failed to rebuild: {module_id}: {self._runtime.last_error}")
                success = False
        return success

    def build_module(self, module_id: str) -> bool:
        self._ensure_open()
        return self._runtime.build_module(module_id)

    def clean_module(self, module_id: str) -> bool:
        self._ensure_open()
        return self._runtime.clean_module(module_id)

    def rebuild_module(self, module_id: str) -> bool:
        self._ensure_open()
        return self._runtime.rebuild_module(module_id)

    def unload_module(self, module_id: str) -> bool:
        self._ensure_open()
        return self._runtime.unload_module(module_id)

    def load_module(self, module_id: str) -> bool:
        self._ensure_open()
        return self._runtime.load_module(module_id)

    def load_descriptor(self, descriptor_path: str | Path) -> bool:
        self._ensure_open()
        descriptor = Path(descriptor_path).resolve()

        if self._project_root is None:
            self._project_root = descriptor.parent

        self._update_environment()
        self._configure_discovery_ignored_roots()
        self._runtime.discover(self._project_root)
        record = self.find_by_descriptor(descriptor)
        if record is None:
            log.error(f"[ProjectModulesRuntime] descriptor is not part of discovered project: {descriptor}")
            return False
        success = self._runtime.load_module(record.id)
        if success:
            self._dirty_module_reasons.pop(record.id, None)
        return success

    def close(self) -> None:
        if self._closed:
            return

        try:
            self._shutdown_runtime()
        finally:
            self._detach_runtime_callbacks()
            self._listeners.clear()
            self._build_output_listeners.clear()
            self._closed = True

    def __enter__(self) -> ProjectModulesRuntime:
        self._ensure_open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def find_by_descriptor(self, descriptor_path: str | Path) -> ModuleRecord | None:
        target = Path(descriptor_path).resolve()
        for record in self.records():
            if Path(record.descriptor_path).resolve() == target:
                return record
        return None

    def _python_record_owns_path(self, record: ModuleRecord, target: Path) -> bool:
        descriptor = Path(record.descriptor_path).resolve()
        if target == descriptor:
            return True

        root_text = record.python_root
        if not root_text:
            return False
        root = Path(root_text).resolve()

        for package_name in record.python_packages:
            if not package_name:
                log.error(f"[ProjectModulesRuntime] Python module '{record.id}' has an empty package name")
                continue
            package_rel = Path(*package_name.split("."))
            package_dir = root / package_rel
            package_module = package_dir.with_suffix(".py")
            if target == package_module:
                return True
            if target == package_dir or package_dir in target.parents:
                return True
        return False

    def _cpp_record_owns_path(self, record: ModuleRecord, target: Path) -> bool:
        descriptor = Path(record.descriptor_path).resolve()
        module_dir = descriptor.parent
        if target == descriptor:
            return True
        if target != module_dir and module_dir not in target.parents:
            return False
        return not self._is_module_input_ignored(target, module_dir)

    def _is_module_input_ignored(self, target: Path, module_dir: Path) -> bool:
        try:
            relative_parts = target.relative_to(module_dir).parts
        except ValueError:
            return True

        for part in relative_parts[:-1]:
            if part in {"build", "__pycache__"}:
                return True
            if part.startswith("."):
                return True
        return False

    def _dispatch_event(self, event: ModuleEvent) -> None:
        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception as e:
                log.error(f"[ProjectModulesRuntime] event listener failed: {e}")

    def _configure_environment(self) -> None:
        environment = ModuleEnvironment()

        # Use the canonical SDK discovery helper shared with all subpackages.
        # find_sdk() checks $TERMIN_SDK → /opt/termin → %LOCALAPPDATA%/termin-sdk,
        # returning the install prefix directly — no fragile `__file__` walk-up.
        from termin_nanobind.runtime import find_sdk
        prefix_root = find_sdk()
        if prefix_root is None:
            raise RuntimeError(
                "termin SDK not found. Set TERMIN_SDK or install to /opt/termin."
            )

        override = os.environ.get("TERMIN_MODULES_PYTHON")
        if override:
            environment.python_executable = override
        else:
            sdk_python = _sdk_python_executable(prefix_root)
            if sdk_python is not None:
                environment.python_executable = str(sdk_python)
            elif _is_python_executable(Path(sys.executable)):
                environment.python_executable = sys.executable
            else:
                log.error(
                    "[ProjectModulesRuntime] SDK Python executable was not found. "
                    f"Expected bundled interpreter under {prefix_root / 'python'}; "
                    "rebuild SDK or set TERMIN_MODULES_PYTHON."
                )
                environment.python_executable = ""

        environment.sdk_prefix = str(prefix_root)
        environment.cmake_prefix_path = str(prefix_root)
        environment.lib_dir = str(prefix_root / "lib")
        environment.allow_python_package_install = True
        environment.use_project_venv = False
        environment.sync_live_scenes = True
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
        self_ref = weakref.ref(self)

        def dispatch_event(event: ModuleEvent) -> None:
            runtime = self_ref()
            if runtime is not None:
                runtime._dispatch_event(event)

        def dispatch_build_output(module_id: str, line: str) -> None:
            runtime = self_ref()
            if runtime is not None:
                runtime._on_build_output(module_id, line)

        self._runtime.set_event_callback(dispatch_event)
        self._runtime.set_build_output_callback(dispatch_build_output)

    def _on_build_output(self, module_id: str, line: str) -> None:
        log.info(f"[{module_id}] {line}")
        for listener in list(self._build_output_listeners):
            try:
                listener(module_id, line)
            except Exception as e:
                log.error(f"[ProjectModulesRuntime] build output listener failed: {e}")

    def _recreate_runtime(self) -> None:
        self._detach_runtime_callbacks()
        self._runtime = ModuleRuntime()
        self._runtime.set_environment(self._integration.environment)
        self._configure_runtime()

    def _configure_discovery_ignored_roots(self) -> None:
        if self._project_root is None:
            self._runtime.set_discovery_ignored_roots([])
            return

        from termin.project.ignored_paths import project_ignored_roots

        self._runtime.set_discovery_ignored_roots(list(project_ignored_roots(self._project_root)))

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

    def _detach_runtime_callbacks(self) -> None:
        self._runtime.clear_callbacks()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("ProjectModulesRuntime is closed")


_instance: ProjectModulesRuntime | None = None


def get_project_modules_runtime() -> ProjectModulesRuntime:
    global _instance
    if _instance is None or _instance.closed:
        _instance = ProjectModulesRuntime()
    return _instance


def _close_project_modules_runtime() -> None:
    global _instance
    if _instance is None:
        return
    _instance.close()
    _instance = None


atexit.register(_close_project_modules_runtime)


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
