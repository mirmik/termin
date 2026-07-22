"""Toolkit-neutral project build and run orchestration for the editor."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from tcbase import log


@dataclass(frozen=True)
class ProjectSceneEntry:
    project_root: Path
    scene_name: str
    scene_rel_path: Path


@dataclass(frozen=True)
class ProjectBuildEntry(ProjectSceneEntry):
    output_dir: Path


class ProjectBuildController:
    def __init__(
        self,
        *,
        scene_manager,
        get_current_project_path: Callable[[], str | None],
        get_editor_scene_name: Callable[[], str | None],
        save_scene: Callable[[], None],
        log_to_console: Callable[[str], None],
        show_quest_openxr: Callable[[ProjectBuildEntry], None] | None = None,
    ) -> None:
        self._scene_manager = scene_manager
        self._get_current_project_path = get_current_project_path
        self._get_editor_scene_name = get_editor_scene_name
        self._save_scene = save_scene
        self._log_to_console = log_to_console
        self._show_quest_openxr = show_quest_openxr

    def run_standalone(self) -> None:
        entry = self._prepare_scene_entry(
            action_name="run standalone",
            relative_error="Standalone entry scene must be inside the current project.",
        )
        if entry is None:
            return

        cmd = [
            sys.executable,
            "-m",
            "termin.player",
            str(entry.project_root),
            "--scene",
            entry.scene_rel_path.as_posix(),
        ]
        self._log_to_console(f"Launching standalone: {' '.join(cmd)}")
        try:
            subprocess.Popen(cmd)
        except Exception as e:
            log.error(f"Failed to launch standalone: {e}")
            self._log_to_console(f"Error: {e}")

    def build_project(self) -> None:
        self.build_desktop_bundle_to_default_dist()

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
        self._log_to_console(
            f"Android identity: {result.application_label}, "
            f"version {result.version_name} ({result.version_code})"
        )
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

        if self._show_quest_openxr is None:
            message = "Quest/OpenXR build UI is unavailable in this editor frontend."
            log.error(f"[ProjectBuildController] {message}")
            self._log_to_console(message)
            return
        self._show_quest_openxr(entry)

    def build_desktop_bundle_to_default_dist(self):
        entry = self._prepare_entry(
            action_name="build desktop bundle",
            relative_error="Desktop build entry scene must be inside the current project.",
            output_subdir="desktop",
        )
        if entry is None:
            return None

        try:
            from termin.project_build import build_desktop_project

            result = build_desktop_project(
                project_root=entry.project_root,
                entry_scene=entry.scene_rel_path,
                output_dir=entry.output_dir,
            )
        except Exception as e:
            log.error(f"Desktop build failed: {e}", exc_info=True)
            self._log_to_console(f"Desktop build failed: {e}")
            return None

        diagnostic_count = len(result.diagnostics)
        self._log_to_console(f"Desktop bundle complete: {result.app_manifest_path}")
        self._log_to_console(f"Desktop package: {result.package_result.package_dir}")
        self._log_to_console(f"Desktop runtime: {result.runtime_result.lib_dir.parent}")
        self._log_to_console(f"Desktop diagnostics: {diagnostic_count} diagnostic(s)")
        for diagnostic in result.diagnostics:
            self._log_to_console(
                f"Desktop build {diagnostic.level}: {diagnostic.path}: {diagnostic.message}"
            )
        return result

    def run_build(self) -> None:
        result = self.build_desktop_bundle_to_default_dist()
        if result is None:
            return

        launcher_path = result.runtime_result.launcher_path
        if launcher_path is not None and launcher_path.exists():
            cmd = [str(launcher_path)]
            cwd = str(launcher_path.parent)
        else:
            message = (
                "Desktop bundle launcher is missing after build: "
                f"{launcher_path or result.dist_dir}. Rebuild the desktop runtime bundle."
            )
            log.error(f"[ProjectBuildController] {message}")
            self._log_to_console(f"Run build failed: {message}")
            return
        self._log_to_console(f"Launching build: {' '.join(cmd)}")
        try:
            subprocess.Popen(cmd, cwd=cwd)
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
        scene_entry = self._prepare_scene_entry(
            action_name=action_name,
            relative_error=relative_error,
        )
        if scene_entry is None:
            return None

        from termin.project.settings import ProjectSettingsManager

        build_output_dir = ProjectSettingsManager.instance().settings.build_output_dir
        output_dir = scene_entry.project_root / build_output_dir
        if output_subdir is not None:
            output_dir = output_dir / output_subdir
        output_dir = output_dir / scene_entry.project_root.name

        return ProjectBuildEntry(
            project_root=scene_entry.project_root,
            scene_name=scene_entry.scene_name,
            scene_rel_path=scene_entry.scene_rel_path,
            output_dir=output_dir,
        )

    def _prepare_scene_entry(
        self,
        *,
        action_name: str,
        relative_error: str,
    ) -> ProjectSceneEntry | None:
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

        return ProjectSceneEntry(
            project_root=project_root,
            scene_name=scene_name,
            scene_rel_path=scene_rel_path,
        )
