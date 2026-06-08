"""Project build and run actions for the tcgui editor."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from tcbase import log


@dataclass(frozen=True)
class ProjectBuildEntry:
    project_root: Path
    scene_name: str
    scene_rel_path: Path
    output_dir: Path


class ProjectBuildController:
    def __init__(
        self,
        *,
        scene_manager,
        get_current_project_path: Callable[[], str | None],
        get_editor_scene_name: Callable[[], str | None],
        get_ui: Callable[[], object | None],
        save_scene: Callable[[], None],
        log_to_console: Callable[[str], None],
    ) -> None:
        self._scene_manager = scene_manager
        self._get_current_project_path = get_current_project_path
        self._get_editor_scene_name = get_editor_scene_name
        self._get_ui = get_ui
        self._save_scene = save_scene
        self._log_to_console = log_to_console

    def run_standalone(self) -> None:
        project_path = self._get_current_project_path()
        if project_path is None:
            self._log_to_console("No project open - cannot run standalone.")
            return

        self._save_scene()

        from termin.editor_core.settings import EditorSettings

        cmd = [sys.executable, "-m", "termin.main", "--project", project_path]
        last_scene = EditorSettings.instance().get("last_scene_file")
        if last_scene:
            cmd.extend(["--scene", last_scene])
        self._log_to_console(f"Launching standalone: {' '.join(cmd)}")
        try:
            subprocess.Popen(cmd)
        except Exception as e:
            log.error(f"Failed to launch standalone: {e}")
            self._log_to_console(f"Error: {e}")

    def build_project(self) -> None:
        self.build_project_to_default_dist()

    def build_android(self) -> None:
        entry = self._prepare_entry(
            action_name="build Android APK",
            relative_error="Android build entry scene must be inside the current project.",
            output_subdir="android",
        )
        if entry is None:
            return

        self._log_to_console(f"Android build started: {entry.scene_rel_path}")
        try:
            from termin.project_build import build_android_project

            result = build_android_project(
                project_root=entry.project_root,
                entry_scene=entry.scene_rel_path,
                output_dir=entry.output_dir,
            )
        except Exception as e:
            log.error(f"Android build failed: {e}", exc_info=True)
            self._log_to_console(f"Android build failed: {e}")
            return

        self._log_to_console(f"Android APK: {result.apk_path}")
        self._log_to_console(f"Android applicationId: {result.application_id}")
        self._log_to_console(f"Android launch: {result.application_id}/{result.launch_activity}")
        self._log_to_console(f"Android package: {result.package_result.package_dir}")
        self._log_to_console(f"Android build log: {result.log_path}")
        for diagnostic in result.diagnostics:
            self._log_to_console(
                f"Android build {diagnostic.level}: {diagnostic.path}: {diagnostic.message}"
            )

    def show_quest_openxr_build_dialog(self) -> None:
        entry = self._prepare_entry(
            action_name="build Quest/OpenXR APK",
            relative_error="Quest/OpenXR build entry scene must be inside the current project.",
            output_subdir="quest_openxr",
        )
        if entry is None:
            return

        ui = self._get_ui()
        if ui is None:
            log.error("[ProjectBuildController] Quest/OpenXR build dialog requested before UI exists")
            return

        from termin.editor_tcgui.dialogs.quest_openxr_build_dialog import show_quest_openxr_build_dialog

        show_quest_openxr_build_dialog(
            ui,
            project_root=entry.project_root,
            entry_scene=entry.scene_rel_path,
            output_dir=entry.output_dir,
            on_log=self._log_to_console,
        )

    def build_project_to_default_dist(self):
        entry = self._prepare_entry(
            action_name="build",
            relative_error="Build entry scene must be inside the current project.",
        )
        if entry is None:
            return None

        try:
            from termin.project_builder import build_project
            from termin.render_framework import collect_scene_shader_usages

            scene = self._scene_manager.get_scene(entry.scene_name)
            if scene is None:
                self._log_to_console("No loaded scene - cannot collect shader usages.")
                return None
            shader_usages = collect_scene_shader_usages(scene.scene_handle())

            result = build_project(
                project_root=entry.project_root,
                entry_scene=entry.scene_rel_path,
                output_dir=entry.output_dir,
                compile_shaders=True,
                shader_usages=shader_usages,
            )
        except Exception as e:
            log.error(f"Build failed: {e}")
            self._log_to_console(f"Build failed: {e}")
            return None

        resource_count = len(result.manifest.resources)
        diagnostic_count = len(result.manifest.diagnostics)
        self._log_to_console(f"Build complete: {result.build_json_path}")
        self._log_to_console(
            f"Build manifest: {resource_count} resource(s), {diagnostic_count} diagnostic(s)"
        )
        for diagnostic in result.manifest.diagnostics:
            self._log_to_console(f"Build {diagnostic.level}: {diagnostic.path}: {diagnostic.message}")
        return result

    def run_build(self) -> None:
        result = self.build_project_to_default_dist()
        if result is None:
            return

        cmd = [
            sys.executable,
            "-m",
            "termin.player",
            "--build",
            str(result.build_json_path),
        ]
        self._log_to_console(f"Launching build: {' '.join(cmd)}")
        try:
            subprocess.Popen(cmd, cwd=str(result.output_dir))
        except Exception as e:
            log.error(f"Failed to launch build: {e}")
            self._log_to_console(f"Run build failed: {e}")

    def _prepare_entry(
        self,
        *,
        action_name: str,
        relative_error: str,
        output_subdir: str | None = None,
    ) -> ProjectBuildEntry | None:
        project_path = self._get_current_project_path()
        if project_path is None:
            self._log_to_console(f"No project open - cannot {action_name}.")
            return None

        self._save_scene()

        scene_name = self._get_editor_scene_name()
        scene_path = self._scene_manager.get_scene_path(scene_name) if scene_name else None
        if scene_path is None:
            self._log_to_console(f"No saved scene - cannot {action_name}.")
            return None

        project_root = Path(project_path).resolve()
        scene_path_obj = Path(scene_path).resolve()
        try:
            scene_rel_path = scene_path_obj.relative_to(project_root)
        except ValueError:
            self._log_to_console(relative_error)
            return None

        from termin.project.settings import ProjectSettingsManager

        build_output_dir = ProjectSettingsManager.instance().settings.build_output_dir
        output_dir = project_root / build_output_dir
        if output_subdir is not None:
            output_dir = output_dir / output_subdir
        output_dir = output_dir / project_root.name

        return ProjectBuildEntry(
            project_root=project_root,
            scene_name=scene_name,
            scene_rel_path=scene_rel_path,
            output_dir=output_dir,
        )
