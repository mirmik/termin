"""Toolkit-neutral execution service for selected project build profiles."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Callable

from termin.base import log

from termin.editor_core.build_profiles_model import BuildProfileAction
from termin.project_build import (
    BuildProfile,
    ProfileDiagnostic,
    ToolchainContext,
    compile_profile_build_request,
    inspect_profile_capabilities,
)


_logger = logging.getLogger(__name__)
SceneSaveRequest = Callable[[Callable[[bool], None]], None]


class ProjectBuildController:
    """Execute editor actions through the canonical normalized-profile backend."""

    def __init__(
        self,
        *,
        save_scene: SceneSaveRequest,
        on_output: Callable[[str], None] | None = None,
        toolchain_settings: Callable[[], ToolchainContext] | None = None,
    ) -> None:
        self._save_scene = save_scene
        self._on_output = on_output
        self._toolchain_settings = toolchain_settings or ToolchainContext

    def capability_diagnostics(
        self,
        action: BuildProfileAction,
        profile: BuildProfile,
    ) -> tuple[ProfileDiagnostic, ...]:
        report = self._inspect(profile)
        if action == BuildProfileAction.DRY_RUN:
            return ()
        if action in (BuildProfileAction.BUILD, BuildProfileAction.RUN):
            return report.diagnostics
        adb = report.context.adb
        diagnostics: list[ProfileDiagnostic] = []
        if adb is None or not adb.is_file():
            diagnostics.append(
                ProfileDiagnostic(
                    "capability.adb",
                    "toolchain.adb",
                    "adb executable was not found",
                )
            )
        if action == BuildProfileAction.INSTALL:
            request = compile_profile_build_request(profile, report.context)
            apk_path = self._apk_path(request)
            if not apk_path.is_file():
                diagnostics.append(
                    ProfileDiagnostic(
                        "capability.apk",
                        "deploy.apk",
                        f"built APK does not exist: {apk_path}",
                    )
                )
        return tuple(diagnostics)

    def execute(self, action: BuildProfileAction, profile: BuildProfile) -> None:
        self._emit(f"{action.value.replace('_', ' ').title()} profile: {profile.name}")
        if action in (BuildProfileAction.BUILD, BuildProfileAction.RUN):
            self._request_scene_save(action, profile)
            return
        try:
            if action == BuildProfileAction.DRY_RUN:
                self._dry_run(profile)
            elif action == BuildProfileAction.INSTALL:
                self._install(profile)
            elif action == BuildProfileAction.LAUNCH:
                self._launch(profile)
            else:
                raise AssertionError(f"Unhandled build profile action: {action}")
        except Exception:
            _logger.exception(
                "Build profile action '%s' failed for '%s'",
                action.value,
                profile.name,
            )
            raise

    def _request_scene_save(
        self,
        action: BuildProfileAction,
        profile: BuildProfile,
    ) -> None:
        def continue_after_save(saved: bool) -> None:
            if not saved:
                message = (
                    f"{action.value.replace('_', ' ').title()} aborted: "
                    "the current scene was not saved"
                )
                _logger.error(message)
                self._emit(message)
                return
            try:
                if action == BuildProfileAction.BUILD:
                    self._build(profile)
                else:
                    self._run(profile)
            except Exception as error:
                _logger.exception(
                    "Build profile action '%s' failed for '%s'",
                    action.value,
                    profile.name,
                )
                self._emit(
                    f"{action.value.replace('_', ' ').title()} failed: {error}"
                )

        try:
            self._save_scene(continue_after_save)
        except Exception as error:
            _logger.exception(
                "Scene save request failed before build profile action '%s' for '%s'",
                action.value,
                profile.name,
            )
            self._emit(
                f"{action.value.replace('_', ' ').title()} aborted: "
                f"scene save failed: {error}"
            )

    def _dry_run(self, profile: BuildProfile) -> None:
        report = self._inspect(profile)
        request = compile_profile_build_request(profile, report.context)
        self._emit(f"Target: {request.target}")
        self._emit(f"Entry scene: {request.context.entry_scene.as_posix()}")
        self._emit(f"Output: {request.context.dist_dir}")
        self._emit(f"Runtime backends: {', '.join(request.runtime_backends)}")
        for diagnostic in report.diagnostics:
            self._emit(f"Capability: {diagnostic.format()}")
        self._emit("Dry run complete; build execution skipped.")

    def _build(self, profile: BuildProfile):
        from termin.project_build import build_profile_result

        result = build_profile_result(
            profile,
            user_settings=self._toolchain_settings(),
            log_callback=self._emit,
        )
        self._report_build(profile, result)
        return result

    def _run(self, profile: BuildProfile) -> None:
        result = self._build(profile)
        launcher_path = result.runtime_result.launcher_path
        if launcher_path is None or not launcher_path.is_file():
            raise FileNotFoundError(f"desktop launcher is missing after build: {launcher_path or result.dist_dir}")
        self._emit(f"Launching: {launcher_path}")
        subprocess.Popen([str(launcher_path)], cwd=str(launcher_path.parent))

    def _install(self, profile: BuildProfile) -> None:
        from termin.project_build import install_android_apk

        report = self._inspect(profile)
        request = compile_profile_build_request(profile, report.context)
        apk_path = self._apk_path(request)
        log_path = request.context.logs_dir / f"{request.target}-deploy.log"
        install_android_apk(
            apk_path,
            adb=request.toolchain.adb,
            log_path=log_path,
            log_callback=self._emit,
        )
        self._emit(f"Install complete: {apk_path}")

    def _launch(self, profile: BuildProfile) -> None:
        from termin.project.settings import load_project_settings
        from termin.project_build import launch_android_app

        report = self._inspect(profile)
        request = compile_profile_build_request(profile, report.context)
        application_id = load_project_settings(request.context.project_root).application.application_id
        log_path = request.context.logs_dir / f"{request.target}-deploy.log"
        launch_android_app(
            application_id,
            adb=request.toolchain.adb,
            log_path=log_path,
            log_callback=self._emit,
            wake_device=request.target == "quest_openxr",
        )
        self._emit(f"Launch command sent: {application_id}")

    def _report_build(self, profile: BuildProfile, result) -> None:
        self._emit(f"Build complete: {result.dist_dir}")
        if profile.target_kind == "desktop":
            self._emit(f"Launcher: {result.runtime_result.launcher_path}")
        else:
            self._emit(f"APK: {result.apk_path}")
            self._emit(f"Application ID: {result.application_id}")
            self._emit(f"Build log: {result.log_path}")
        for diagnostic in result.diagnostics:
            self._emit(f"Build {diagnostic.level}: {diagnostic.path}: {diagnostic.message}")

    def _inspect(self, profile: BuildProfile):
        return inspect_profile_capabilities(
            profile,
            user_settings=self._toolchain_settings(),
        )

    @staticmethod
    def _apk_path(request) -> Path:
        qualifier = "-quest-openxr" if request.target == "quest_openxr" else ""
        return request.context.dist_dir / "apk" / f"{request.context.project_name}{qualifier}-debug.apk"

    def _emit(self, message: str) -> None:
        normalized = str(message)
        log.info(normalized)
        if self._on_output is not None:
            self._on_output(normalized)


__all__ = ["ProjectBuildController"]
