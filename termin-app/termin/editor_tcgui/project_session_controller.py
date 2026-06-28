"""Project session setup for the tcgui editor."""

from __future__ import annotations

import json
import os
import runpy
import sys
from pathlib import Path
from typing import Callable

from tcbase import log
from tcgui.widgets.message_box import MessageBox

from termin.editor_core.settings import EditorSettings


class ProjectSessionController:
    def __init__(
        self,
        *,
        get_ui: Callable[[], object | None],
        set_project_state: Callable[[str, str], None],
        log_to_console: Callable[[str], None],
        rescan_file_resources: Callable[[], None],
        set_project_browser_root: Callable[[str], None],
        get_init_script_editor: Callable[[], object],
        resolve_termin_shaderc: Callable[[], Path | None],
        resolve_slangc: Callable[[], Path | None],
    ) -> None:
        self._get_ui = get_ui
        self._set_project_state = set_project_state
        self._log_to_console = log_to_console
        self._rescan_file_resources = rescan_file_resources
        self._set_project_browser_root = set_project_browser_root
        self._get_init_script_editor = get_init_script_editor
        self._resolve_termin_shaderc = resolve_termin_shaderc
        self._resolve_slangc = resolve_slangc

    def restore_project(self) -> None:
        """Restore project from launcher or last session."""
        from termin.launcher.recent import read_launch_project

        project_file: str | None = None

        launch_path = read_launch_project()
        if launch_path is not None:
            p = Path(launch_path)
            if p.exists() and p.is_file() and p.suffix == ".terminproj":
                project_file = str(p)

        if project_file is None:
            last = EditorSettings.instance().get("last_project_file")
            if last and Path(last).exists():
                project_file = last

        if project_file is not None:
            self.load_project(project_file)
            EditorSettings.instance().set("last_project_file", project_file)

    def create_project_file(self, path: str) -> None:
        if not path:
            return
        project_file = Path(path)
        if project_file.suffix != ".terminproj":
            project_file = project_file.with_suffix(".terminproj")
        try:
            project_data = {
                "version": 1,
                "name": project_file.stem,
            }
            project_file.parent.mkdir(parents=True, exist_ok=True)
            project_file.write_text(json.dumps(project_data, indent=2), encoding="utf-8")
        except Exception as e:
            log.error(f"Failed to create project file {project_file}: {e}")
            ui = self._get_ui()
            if ui is not None:
                MessageBox.error(ui, "Create Project Failed", f"Failed to create project:\n{e}")
            return
        self.load_project(str(project_file))

    def load_project(self, path: str) -> None:
        project_root = Path(path).parent
        project_dir = str(project_root)
        self._set_project_state(project_dir, Path(path).stem)
        self._log_to_console(f"Project: {project_dir}")
        self.configure_shader_runtime_for_project(
            project_root,
            resolve_termin_shaderc=self._resolve_termin_shaderc,
            resolve_slangc=self._resolve_slangc,
        )

        from termin.project.settings import ProjectSettingsManager

        ProjectSettingsManager.instance().set_project_path(project_root)

        from termin.navmesh.settings import NavigationSettingsManager

        NavigationSettingsManager.instance().set_project_path(project_root)

        EditorSettings.instance().set("last_project_file", path)

        self.load_project_modules(project_root)
        self.run_project_init_script(project_root)
        self._rescan_file_resources()
        self._set_project_browser_root(project_dir)

    @staticmethod
    def configure_shader_runtime_for_project(
        project_root: Path,
        *,
        resolve_termin_shaderc: Callable[[], Path | None],
        resolve_slangc: Callable[[], Path | None],
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
            import tgfx

            tgfx.configure_shader_runtime(
                artifact_root=str(artifact_root),
                cache_root=str(cache_root),
                shader_compiler=str(compiler),
                dev_compile=True,
            )
            log.info(
                "[ShaderRuntime] configured: "
                f"artifact_root='{artifact_root}' cache_root='{cache_root}' "
                f"compiler='{compiler}' slangc='{slangc}' dev_compile=True"
            )
        except Exception as e:
            log.error(f"[ShaderRuntime] configure_shader_runtime failed: {e}")

    def load_project_modules(self, project_root: Path) -> None:
        from termin.modules.runtime import get_project_modules_runtime
        from termin_modules import ModuleKind, ModuleState

        runtime = get_project_modules_runtime()
        success = runtime.load_project(project_root)
        if not success and runtime.last_error:
            self._log_to_console(f"Module load error: {runtime.last_error}")

        cpp_loaded = 0
        cpp_failed = 0
        py_loaded = 0
        py_failed = 0

        for record in runtime.records():
            if record.kind == ModuleKind.Cpp:
                if record.state == ModuleState.Loaded:
                    cpp_loaded += 1
                    self._log_to_console(f"Loaded C++ module: {record.id}")
                elif record.state == ModuleState.Failed:
                    cpp_failed += 1
                    self._log_to_console(
                        f"Failed to load C++ module {record.id}: {record.error_message}"
                    )
            else:
                if record.state == ModuleState.Loaded:
                    py_loaded += 1
                    self._log_to_console(f"Loaded Python module: {record.id}")
                elif record.state == ModuleState.Failed:
                    py_failed += 1
                    self._log_to_console(
                        f"Failed to load Python module {record.id}: {record.error_message}"
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
