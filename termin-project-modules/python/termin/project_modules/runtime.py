from __future__ import annotations

import atexit
import os
import subprocess
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
    ModuleState,
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
    return name in {
        "python",
        "python3",
        "python.exe",
        "pythonw.exe",
        "termin_python",
        "termin_python.exe",
    } or name.startswith("python3.")


def _sdk_python_executable(prefix_root: Path) -> Path | None:
    if sys.platform == "win32":
        candidates = (
            prefix_root / "python" / "python.exe",
            prefix_root / "bin" / "python.exe",
            prefix_root / "bin" / "termin_python.exe",
        )
    else:
        candidates = (
            prefix_root / "bin" / "termin_python",
            prefix_root / "bin" / "python3",
            prefix_root / "bin" / "python",
        )

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


class ProjectModulesRuntime:
    def __init__(self, scene_manager=None) -> None:
        self._project_root: Path | None = None
        self._integration = TermModulesIntegration()
        self._scene_manager = scene_manager
        if scene_manager is not None:
            self._integration.set_scene_manager(scene_manager)
        self._runtime = ModuleRuntime()
        self._listeners: list[Callable[[ModuleEvent], None]] = []
        self._build_output_listeners: list[Callable[[str, str], None]] = []
        self._dirty_module_reasons: dict[str, set[str]] = {}
        self._background_error = ""
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
        return self._background_error or self._runtime.last_error

    @property
    def sync_live_scenes(self) -> bool:
        return bool(self._integration.environment.sync_live_scenes)

    def set_sync_live_scenes(self, enabled: bool) -> None:
        if enabled and self._scene_manager is None:
            raise RuntimeError("live scene synchronization requires an explicit SceneManager")
        environment = self._integration.environment
        environment.sync_live_scenes = bool(enabled)
        self._integration.set_environment(environment)
        self._runtime.set_environment(environment)
        self._integration.configure_runtime(self._runtime)

    def set_scene_manager(self, scene_manager) -> None:
        self._ensure_open()
        if scene_manager is None:
            raise ValueError("scene_manager must not be None")
        self._scene_manager = scene_manager
        self._integration.set_scene_manager(scene_manager)
        environment = self._integration.environment
        environment.sync_live_scenes = True
        self._integration.set_environment(environment)
        self._runtime.set_environment(environment)
        self._integration.configure_runtime(self._runtime)

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
        next_project_root = (
            Path(project_root).resolve() if project_root is not None else self._project_root
        )

        if next_project_root is None:
            log.error("[ProjectModulesRuntime] project root is not set")
            return False

        if not self._shutdown_runtime():
            return False
        self._project_root = next_project_root
        self._update_environment()
        self._recreate_runtime()
        self._configure_discovery_ignored_roots()
        if not self._runtime.discover(self._project_root):
            log.error(f"[ProjectModulesRuntime] discover failed: {self._runtime.last_error}")
            return False
        success = self._runtime.load_all()
        if success:
            self._dirty_module_reasons.clear()
        return success

    def discover_project(self, project_root: str | Path | None = None) -> bool:
        self._ensure_open()
        next_project_root = (
            Path(project_root).resolve() if project_root is not None else self._project_root
        )

        if next_project_root is None:
            log.error("[ProjectModulesRuntime] project root is not set")
            return False

        if not self._shutdown_runtime():
            return False
        self._project_root = next_project_root
        self._update_environment()
        self._recreate_runtime()
        self._configure_discovery_ignored_roots()
        return bool(self._runtime.discover(self._project_root))

    def reload_module(self, module_id: str) -> bool:
        self._ensure_open()
        self._background_error = ""
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

    def changed_modules(self) -> list[str]:
        """Return dirty or stale module IDs in runtime record order."""
        pending = set(self._dirty_module_reasons)
        pending.update(self.stale_modules())
        return [record.id for record in self.records() if record.id in pending]

    def reload_dirty_modules(self) -> bool:
        """Reload modules with pending code changes. Returns True if all succeeded."""
        self._ensure_open()
        pending = set(self.changed_modules())
        if not pending:
            return True

        success = True
        while pending:
            module_id = self._first_pending_module(pending)
            if module_id is None:
                break

            affected = self._loaded_dependent_closure(module_id)
            log.info(f"[ProjectModulesRuntime] Reloading changed module: {module_id}")
            if not self.reload_module(module_id):
                log.error(
                    f"[ProjectModulesRuntime] Failed to reload changed module '{module_id}': "
                    f"{self._runtime.last_error}"
                )
                success = False
                break

            for affected_id in affected:
                self._dirty_module_reasons.pop(affected_id, None)
            pending.difference_update(affected)
            pending = {module_id for module_id in pending if self.find(module_id) is not None}

        return success

    def prepare_changed_modules_for_play(self) -> bool:
        """Apply pending module changes before entering Play mode."""
        return self.reload_dirty_modules()

    def rebuild_stale_modules(self) -> bool:
        """Rebuild all modules that need it. Returns True if all succeeded."""
        return self.reload_dirty_modules()

    def build_module(self, module_id: str) -> bool:
        self._ensure_open()
        self._background_error = ""
        return self._runtime.build_module(module_id)

    def clean_module(self, module_id: str) -> bool:
        self._ensure_open()
        return self._runtime.clean_module(module_id)

    def rebuild_module(self, module_id: str) -> bool:
        self._ensure_open()
        self._background_error = ""
        return self._runtime.rebuild_module(module_id)

    def prepare_module_artifacts(
        self,
        *,
        project_root: str | Path | None = None,
        operation: str = "warmup",
        module_id: str | None = None,
    ) -> bool:
        """Build project module artifacts in an isolated worker process.

        This method is safe to call from an editor worker: the subprocess owns
        its own module runtime and cannot mutate this process' scenes or global
        registries. The editor must perform the subsequent load/reload commit on
        its owner thread.
        """
        self._ensure_open()
        self._background_error = ""
        target_root = Path(project_root).resolve() if project_root is not None else self._project_root
        if target_root is None:
            self._background_error = "Project root is not set for module artifact preparation"
            log.error(f"[ProjectModulesRuntime] {self._background_error}")
            return False

        python_executable = self._integration.environment.python_executable
        if not python_executable:
            self._background_error = "SDK Python executable is not configured"
            log.error(f"[ProjectModulesRuntime] {self._background_error}")
            return False

        command = [
            python_executable,
            "-m",
            "termin.project_modules.warmup",
            "warmup",
            "--project",
            str(target_root),
            "--quiet",
        ]
        operation_flags = {
            "warmup": None,
            "build": "--build-module",
            "clean": "--clean-module",
            "rebuild": "--rebuild-module",
        }
        if operation not in operation_flags:
            raise ValueError(f"Unsupported module artifact operation: {operation}")
        flag = operation_flags[operation]
        if flag is not None:
            if not module_id:
                raise ValueError(f"Module id is required for artifact operation '{operation}'")
            command.extend([flag, module_id])

        try:
            process = subprocess.Popen(
                command,
                cwd=target_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            assert process.stdout is not None
            for raw_line in process.stdout:
                line = raw_line.rstrip("\r\n")
                if line:
                    self._on_build_output("module-build", line)
            return_code = process.wait()
        except Exception as exc:
            self._background_error = f"Failed to run isolated module build: {exc}"
            log.error(f"[ProjectModulesRuntime] {self._background_error}", exc_info=True)
            return False

        if return_code != 0:
            self._background_error = f"Isolated module build failed with exit code {return_code}"
            log.error(f"[ProjectModulesRuntime] {self._background_error}")
            return False
        return True

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

        existing = self.find_by_descriptor(descriptor)
        if existing is not None:
            success = self._runtime.load_module(existing.id)
            if success:
                self._dirty_module_reasons.pop(existing.id, None)
            return success

        # A new descriptor changes the dependency graph. Rebuild the runtime
        # through its explicit shutdown boundary instead of rediscovering over
        # live backend handles and orphaning the previous records.
        if not self.load_project(self._project_root):
            return False
        record = self.find_by_descriptor(descriptor)
        if record is None:
            log.error(f"[ProjectModulesRuntime] descriptor is not part of discovered project: {descriptor}")
            return False
        success = self._runtime.load_module(record.id)
        if success:
            self._dirty_module_reasons.pop(record.id, None)
        return success

    def close(self) -> bool:
        if self._closed:
            return True

        if not self._shutdown_runtime():
            return False
        self._detach_runtime_callbacks()
        self._integration.clear_scene_provider()
        self._scene_manager = None
        self._listeners.clear()
        self._build_output_listeners.clear()
        self._closed = True
        return True

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

    def _first_pending_module(self, pending: set[str]) -> str | None:
        for record in self.records():
            if record.id in pending:
                return record.id
        return next(iter(pending), None)

    def _loaded_dependent_closure(self, module_id: str) -> set[str]:
        affected = {module_id}
        changed = True
        while changed:
            changed = False
            for record in self.records():
                if record.id in affected:
                    continue
                if not self._record_is_loaded(record):
                    continue
                if any(dependency in affected for dependency in record.dependencies):
                    affected.add(record.id)
                    changed = True
        return affected

    def _record_is_loaded(self, record: ModuleRecord) -> bool:
        return record.state == ModuleState.Loaded

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
                    f"Expected bundled Python under {prefix_root}; "
                    "rebuild SDK or set TERMIN_MODULES_PYTHON."
                )
                environment.python_executable = ""

        environment.sdk_prefix = str(prefix_root)
        environment.cmake_prefix_path = str(prefix_root)
        environment.lib_dir = str(prefix_root / "lib")
        environment.allow_python_package_install = True
        environment.use_project_venv = False
        environment.sync_live_scenes = self._scene_manager is not None
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

    def _shutdown_runtime(self) -> bool:
        if self._runtime.shutdown():
            return True
        log.error(f"[ProjectModulesRuntime] runtime shutdown failed: {self._runtime.last_error}")
        return False

    def _detach_runtime_callbacks(self) -> None:
        self._runtime.clear_callbacks()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("ProjectModulesRuntime is closed")


_instance: ProjectModulesRuntime | None = None


def get_project_modules_runtime(scene_manager=None) -> ProjectModulesRuntime:
    global _instance
    if _instance is None or _instance.closed:
        _instance = ProjectModulesRuntime(scene_manager=scene_manager)
    elif scene_manager is not None and _instance._scene_manager is not scene_manager:
        _instance.set_scene_manager(scene_manager)
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
