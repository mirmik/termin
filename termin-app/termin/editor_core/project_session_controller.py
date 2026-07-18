"""Toolkit-neutral project session lifecycle for editor frontends."""

from __future__ import annotations

import json
import os
import runpy
import sys
from pathlib import Path
from typing import Callable

from tcbase import log
from termin.editor_core.project_operations import sync_stdlib
from termin.editor_core.settings import EditorSettings


class ProjectSessionController:
    def __init__(
        self,
        *,
        set_project_state: Callable[[str, str], None],
        log_to_console: Callable[[str], None],
        rescan_file_resources: Callable[[], None],
        set_project_browser_root: Callable[[str], None],
        get_init_script_editor: Callable[[], object],
        resolve_termin_shaderc: Callable[[], Path | None],
        resolve_slangc: Callable[[], Path | None],
        get_render_engine: Callable[[], object],
        show_error: Callable[[str, str], None] | None = None,
        run_module_operation: Callable[[object, Path, Callable[[bool], None]], None]
        | None = None,
    ) -> None:
        self._set_project_state = set_project_state
        self._log_to_console = log_to_console
        self._rescan_file_resources = rescan_file_resources
        self._set_project_browser_root = set_project_browser_root
        self._get_init_script_editor = get_init_script_editor
        self._resolve_termin_shaderc = resolve_termin_shaderc
        self._resolve_slangc = resolve_slangc
        self._get_render_engine = get_render_engine
        self._show_error = show_error
        self._run_module_operation = run_module_operation
        self._project_file: Path | None = None
        self._initializing = False

    @property
    def project_file(self) -> Path | None:
        return self._project_file

    def restore_project(
        self,
        on_complete: Callable[[bool], None] | None = None,
    ) -> bool:
        """Restore project from launcher or last session."""
        from termin.launcher.recent import read_launch_project

        project_file: str | None = None

        launch_path = read_launch_project()
        if launch_path is not None:
            p = Path(launch_path)
            if p.exists() and p.is_file() and p.suffix == ".terminproj":
                project_file = str(p)

        if project_file is None:
            last = EditorSettings.instance().get_last_project_file()
            if last is not None:
                project_file = str(last)

        if project_file is not None:
            return self.initialize_project(project_file, on_complete=on_complete)
        return False

    def initialize_project(
        self,
        path: str,
        on_complete: Callable[[bool], None] | None = None,
    ) -> bool:
        """Initialize the editor's single project session.

        Descriptor validation and stdlib synchronization happen before any
        process-global or frontend state is published.  Once publication has
        begun, this controller permanently owns that project for the lifetime
        of the editor process, including when module loading leaves the project
        in a degraded state.
        """
        if self._project_file is not None or self._initializing:
            current = self._project_file or Path(path)
            self._report_error(
                "Project Already Initialized",
                f"This editor process already owns project session: {current}",
            )
            if on_complete is not None:
                on_complete(False)
            return False

        try:
            project_file, project_name = self._validate_project_descriptor(path)
        except Exception as e:
            self._report_error(
                "Project Validation Failed",
                f"Cannot initialize project '{path}': {e}",
            )
            if on_complete is not None:
                on_complete(False)
            return False

        project_root = project_file.parent
        try:
            sync_stdlib(project_root)
        except Exception as e:
            self._report_error(
                "Standard Library Sync Failed",
                f"Failed to sync project stdlib for '{project_root}': {e}",
            )
            if on_complete is not None:
                on_complete(False)
            return False

        self._initializing = True
        self._project_file = project_file
        project_dir = str(project_root)

        try:
            from termin.editor_core.project_context import set_current_project_path

            set_current_project_path(project_root)
            self.configure_shader_runtime_for_project(
                project_root,
                resolve_termin_shaderc=self._resolve_termin_shaderc,
                resolve_slangc=self._resolve_slangc,
                render_engine=self._get_render_engine(),
            )

            from termin.project.settings import ProjectSettingsManager

            ProjectSettingsManager.instance().set_project_path(project_root)

            from termin.navmesh.settings import NavigationSettingsManager

            NavigationSettingsManager.instance().set_project_path(project_root)
            EditorSettings.instance().set_last_project_file(project_file)

            self._set_project_state(project_dir, project_name)
            self._set_project_browser_root(project_dir)
            self._rescan_file_resources()
            self._log_to_console(f"Project: {project_dir}")
        except Exception as e:
            self._initializing = False
            self._report_error(
                "Project Initialization Failed",
                f"Failed to publish project session '{project_file}': {e}",
            )
            if on_complete is not None:
                on_complete(False)
            return False

        module_load_finished = False

        def finish_project_load(success: bool) -> None:
            nonlocal module_load_finished
            if module_load_finished:
                log.error(
                    "[ProjectSessionController] module operation completed more than once "
                    f"for {project_file}"
                )
                return
            module_load_finished = True
            self._initializing = False
            if success:
                self.run_project_init_script(project_root)
            else:
                self._report_error(
                    "Project Module Load Failed",
                    f"Project '{project_file}' is open in degraded mode because its modules failed to load.",
                )
            if on_complete is not None:
                on_complete(success)

        try:
            self.load_project_modules(project_root, on_complete=finish_project_load)
        except Exception as e:
            if not module_load_finished:
                module_load_finished = True
                self._initializing = False
                self._report_error(
                    "Project Module Load Failed",
                    f"Project '{project_file}' is open in degraded mode: {e}",
                )
                if on_complete is not None:
                    on_complete(False)
            else:
                log.error(
                    "[ProjectSessionController] module operation raised after completion "
                    f"for {project_file}: {e}"
                )
        return True

    @staticmethod
    def _validate_project_descriptor(path: str) -> tuple[Path, str]:
        project_file = Path(path).expanduser().resolve(strict=True)
        if not project_file.is_file():
            raise ValueError("project descriptor is not a regular file")
        if project_file.suffix != ".terminproj":
            raise ValueError("project descriptor must have the .terminproj extension")
        with project_file.open("r", encoding="utf-8") as stream:
            descriptor = json.load(stream)
        if not isinstance(descriptor, dict):
            raise ValueError("project descriptor root must be an object")
        if descriptor.get("version") != 1:
            raise ValueError("project descriptor version must be 1")
        project_name = descriptor.get("name")
        if not isinstance(project_name, str) or not project_name.strip():
            raise ValueError("project descriptor name must be a non-empty string")
        return project_file, project_name.strip()

    def _report_error(self, title: str, message: str) -> None:
        log.error(f"[ProjectSessionController] {title}: {message}")
        self._log_to_console(f"{title}: {message}")
        if self._show_error is not None:
            self._show_error(title, message)

    @staticmethod
    def configure_shader_runtime_for_project(
        project_root: Path,
        *,
        resolve_termin_shaderc: Callable[[], Path | None],
        resolve_slangc: Callable[[], Path | None],
        render_engine,
    ) -> None:
        artifact_root = project_root / ".termin" / "shader-artifacts"
        cache_root = project_root / ".termin" / "shader-cache"
        compiler = resolve_termin_shaderc()
        if compiler is None:
            log.error(
                "[ShaderRuntime] termin_shaderc not found; Slang runtime "
                "shader compilation is unavailable. Set TERMIN_SHADERC or TERMIN_SDK."
            )
            return
        slangc = resolve_slangc()
        if slangc is None:
            log.error(
                "[ShaderRuntime] slangc not found; Slang runtime shader "
                "compilation is unavailable. Set TERMIN_SLANGC, add slangc to PATH, "
                "install it under TERMIN_SDK/bin, or configure Shader/slangCompiler "
                "in editor settings."
            )
            return

        artifact_root.mkdir(parents=True, exist_ok=True)
        cache_root.mkdir(parents=True, exist_ok=True)
        os.environ["TERMIN_SLANGC"] = str(slangc)

        try:
            render_engine.configure_shader_artifacts(
                artifact_root=str(artifact_root),
                cache_root=str(cache_root),
                compiler_path=str(compiler),
                dev_compile_enabled=True,
            )
            log.info(
                "[ShaderRuntime] configured: "
                f"artifact_root='{artifact_root}' cache_root='{cache_root}' "
                f"compiler='{compiler}' slangc='{slangc}' dev_compile=True"
            )
        except Exception as e:
            log.error(f"[ShaderRuntime] render engine shader configuration failed: {e}")

    def load_project_modules(
        self,
        project_root: Path,
        on_complete: Callable[[bool], None] | None = None,
    ) -> None:
        from termin.project_modules.runtime import get_project_modules_runtime
        from termin_modules import ModuleKind, ModuleState

        runtime = get_project_modules_runtime()

        def finish(success: bool) -> None:
            if not success and runtime.last_error:
                self._log_to_console(f"Module load error: {runtime.last_error}")
            self._log_project_module_summary(runtime, ModuleKind, ModuleState)
            if on_complete is not None:
                on_complete(success)

        if self._run_module_operation is not None:
            self._run_module_operation(runtime, project_root, finish)
            return

        success = runtime.load_project(project_root)
        finish(success)

    def _log_project_module_summary(self, runtime, ModuleKind, ModuleState) -> None:

        cpp_loaded = 0
        cpp_failed = 0
        py_loaded = 0
        py_failed = 0

        for record in runtime.records():
            if record.kind == ModuleKind.Cpp:
                if record.state == ModuleState.Loaded:
                    cpp_loaded += 1
                    self._log_to_console(f"Loaded C++ module: {record.id}")
                elif record.state in (ModuleState.Failed, ModuleState.CleanupFailed):
                    cpp_failed += 1
                    self._log_to_console(
                        f"C++ module {record.id} is not active: {record.error_message}"
                    )
            else:
                if record.state == ModuleState.Loaded:
                    py_loaded += 1
                    self._log_to_console(f"Loaded Python module: {record.id}")
                elif record.state in (ModuleState.Failed, ModuleState.CleanupFailed):
                    py_failed += 1
                    self._log_to_console(
                        f"Python module {record.id} is not active: {record.error_message}"
                    )

        if cpp_loaded > 0:
            self._log_to_console(f"Loaded {cpp_loaded} C++ module(s)")
        if cpp_failed > 0:
            self._log_to_console(f"Failed to load {cpp_failed} C++ module(s)")
        if py_loaded > 0:
            self._log_to_console(f"Loaded {py_loaded} Python module(s)")
        if py_failed > 0:
            self._log_to_console(f"Failed to load {py_failed} Python module(s)")

    def run_project_init_script(self, project_root: Path) -> None:
        init_script = project_root / "InitScript.py"
        if not init_script.is_file():
            return

        project_path = str(project_root)
        inserted_project_path = False
        if project_path not in sys.path:
            sys.path.insert(0, project_path)
            inserted_project_path = True

        try:
            runpy.run_path(
                str(init_script),
                init_globals={
                    "editor": self._get_init_script_editor(),
                    "project_root": project_root,
                },
            )
        except Exception as e:
            log.error(f"Project init script failed: {init_script}: {e}")
            self._log_to_console(f"Project init script failed: {e}")
        finally:
            if inserted_project_path:
                sys.path.remove(project_path)
