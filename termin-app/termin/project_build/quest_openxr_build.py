"""Quest/OpenXR project build and deployment helpers."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from termin.project_build.common import preload_project_resources, read_project_name
from termin.project_build.runtime_package_exporter import (
    RuntimePackageExportDiagnostic,
    RuntimePackageExportResult,
    export_runtime_package,
)
from termin.project_build.runtime_package_validator import validate_runtime_package
from termin.project_build.target_build_common import read_log_tail
from termin.project_build.target_preflight import preflight_quest_openxr_build


QUEST_OPENXR_APPLICATION_ID = "org.termin.openxr"
QUEST_OPENXR_LAUNCH_ACTIVITY = "android.app.NativeActivity"


@dataclass
class QuestOpenXRBuildResult:
    dist_dir: Path
    package_result: RuntimePackageExportResult
    apk_path: Path
    log_path: Path
    application_id: str = QUEST_OPENXR_APPLICATION_ID
    launch_activity: str = QUEST_OPENXR_LAUNCH_ACTIVITY
    diagnostics: list[RuntimePackageExportDiagnostic] = field(default_factory=list)


@dataclass
class QuestOpenXRDeployResult:
    command: list[str]
    log_path: Path | None
    output: str


def build_quest_openxr_project(
    project_root: str | Path,
    entry_scene: str | Path,
    output_dir: str | Path | None = None,
    termin_root: str | Path | None = None,
    build_script: str | Path | None = None,
    gradle: str | Path | None = None,
    shader_compiler: str | Path | None = None,
    default_shader_language: str = "slang",
    abi: str = "arm64-v8a",
    platform: str = "android-26",
    log_callback: Callable[[str], None] | None = None,
) -> QuestOpenXRBuildResult:
    project_root_path = Path(project_root).resolve()
    project_name = read_project_name(project_root_path)
    dist_dir = _resolve_quest_dist_dir(project_root_path, project_name, output_dir)
    package_dir = dist_dir / "package"
    apk_dir = dist_dir / "apk"
    logs_dir = dist_dir / "logs"
    apk_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    preflight_result = preflight_quest_openxr_build(
        termin_root=termin_root,
        build_script=build_script,
        gradle=gradle,
        abi=abi,
        platform=platform,
    )

    preload_project_resources(project_root_path, "[QuestOpenXRBuild]")

    package_result = export_runtime_package(
        project_root=project_root_path,
        entry_scene=entry_scene,
        output_dir=package_dir,
        shader_compiler=shader_compiler,
        default_shader_language=default_shader_language,
    )
    package_validation_diagnostics = validate_runtime_package(package_result.package_dir)

    log_path = logs_dir / "quest-openxr-build.log"
    _run_quest_build_script(
        build_script=preflight_result.build_script,
        package_dir=package_result.package_dir,
        log_path=log_path,
        gradle=preflight_result.gradle,
        android_sdk_root=preflight_result.android_sdk_root,
        abi=abi,
        platform=platform,
        log_callback=log_callback,
    )

    source_apk = (
        preflight_result.termin_root
        / "build"
        / "android-gradle-openxr"
        / "app"
        / "outputs"
        / "apk"
        / "debug"
        / "app-debug.apk"
    )
    if not source_apk.exists():
        raise FileNotFoundError(f"Quest/OpenXR build did not produce APK: {source_apk}")

    apk_path = apk_dir / f"{project_name}-quest-openxr-debug.apk"
    shutil.copy2(source_apk, apk_path)

    return QuestOpenXRBuildResult(
        dist_dir=dist_dir,
        package_result=package_result,
        apk_path=apk_path,
        log_path=log_path,
        diagnostics=[
            *preflight_result.diagnostics,
            *package_result.diagnostics,
            *package_validation_diagnostics,
        ],
    )


def install_quest_openxr_apk(
    apk_path: str | Path,
    adb: str | Path | None = None,
    log_path: str | Path | None = None,
    log_callback: Callable[[str], None] | None = None,
) -> QuestOpenXRDeployResult:
    apk = Path(apk_path).resolve()
    if not apk.exists():
        raise FileNotFoundError(f"Quest/OpenXR APK does not exist: {apk}")

    adb_bin = _resolve_adb(adb)
    cmd = [str(adb_bin), "install", "-r", str(apk)]
    return _run_deploy_command(cmd, log_path, log_callback)


def launch_quest_openxr_app(
    adb: str | Path | None = None,
    log_path: str | Path | None = None,
    log_callback: Callable[[str], None] | None = None,
) -> list[QuestOpenXRDeployResult]:
    adb_bin = _resolve_adb(adb)
    return [
        _run_deploy_command(
            [str(adb_bin), "shell", "input", "keyevent", "KEYCODE_WAKEUP"],
            log_path,
            log_callback,
        ),
        _run_deploy_command(
            [str(adb_bin), "shell", "monkey", "-p", QUEST_OPENXR_APPLICATION_ID, "1"],
            log_path,
            log_callback,
        ),
    ]


def default_quest_openxr_apk_path(
    project_root: str | Path,
    output_dir: str | Path | None = None,
) -> Path:
    project_root_path = Path(project_root).resolve()
    project_name = read_project_name(project_root_path)
    dist_dir = _resolve_quest_dist_dir(project_root_path, project_name, output_dir)
    return dist_dir / "apk" / f"{project_name}-quest-openxr-debug.apk"


def default_quest_openxr_log_path(
    project_root: str | Path,
    output_dir: str | Path | None = None,
) -> Path:
    project_root_path = Path(project_root).resolve()
    project_name = read_project_name(project_root_path)
    dist_dir = _resolve_quest_dist_dir(project_root_path, project_name, output_dir)
    return dist_dir / "logs" / "quest-openxr-deploy.log"


def _resolve_quest_dist_dir(project_root: Path, project_name: str, output_dir: str | Path | None) -> Path:
    if output_dir is not None:
        return Path(output_dir).resolve()
    return (project_root / "dist" / "quest_openxr" / project_name).resolve()


def _run_quest_build_script(
    build_script: Path,
    package_dir: Path,
    log_path: Path,
    gradle: Path | None,
    android_sdk_root: Path,
    abi: str,
    platform: str,
    log_callback: Callable[[str], None] | None,
) -> None:
    cmd = [
        str(build_script),
        "--assets-dir",
        str(package_dir),
        "--sdk-root",
        str(android_sdk_root),
        "--abi",
        abi,
        "--platform",
        platform,
    ]
    if gradle is not None:
        cmd.extend(["--gradle", str(gradle)])

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("", encoding="utf-8")
    returncode = _run_logged_process(cmd, log_path, log_callback)
    if returncode != 0:
        log_tail = read_log_tail(log_path)
        raise RuntimeError(
            f"Quest/OpenXR build failed with exit code {returncode}; see {log_path}\n{log_tail}"
        )


def _resolve_adb(adb: str | Path | None) -> Path:
    if adb is not None:
        adb_text = str(adb)
        adb_path = Path(adb_text).expanduser()
        if adb_path.exists():
            return adb_path.resolve()
        found_adb = shutil.which(adb_text)
        if found_adb is not None:
            return Path(found_adb).resolve()
        raise FileNotFoundError(f"adb executable does not exist: {adb_text}")

    env_adb = os.environ.get("ADB")
    if env_adb:
        adb_path = Path(env_adb).expanduser()
        if adb_path.exists():
            return adb_path.resolve()
        found_adb = shutil.which(env_adb)
        if found_adb is not None:
            return Path(found_adb).resolve()
        raise FileNotFoundError(f"ADB points to a missing executable: {env_adb}")

    found = shutil.which("adb")
    if found is None:
        raise FileNotFoundError("adb executable not found. Set ADB or add adb to PATH.")
    return Path(found).resolve()


def _run_deploy_command(
    cmd: list[str],
    log_path: str | Path | None,
    log_callback: Callable[[str], None] | None,
) -> QuestOpenXRDeployResult:
    resolved_log_path: Path | None = None
    if log_path is not None:
        resolved_log_path = Path(log_path).resolve()
        resolved_log_path.parent.mkdir(parents=True, exist_ok=True)
    output, returncode = _run_logged_process_capture(cmd, resolved_log_path, log_callback)

    if returncode != 0:
        raise RuntimeError(
            f"Quest/OpenXR deploy command failed with exit code {returncode}: {' '.join(cmd)}\n{output}"
        )

    return QuestOpenXRDeployResult(
        command=cmd,
        log_path=resolved_log_path,
        output=output,
    )


def _run_logged_process(
    cmd: list[str],
    log_path: Path,
    log_callback: Callable[[str], None] | None,
) -> int:
    output, returncode = _run_logged_process_capture(cmd, log_path, log_callback)
    return returncode


def _run_logged_process_capture(
    cmd: list[str],
    log_path: Path | None,
    log_callback: Callable[[str], None] | None,
) -> tuple[str, int]:
    output_lines: list[str] = []
    log_file = None
    try:
        if log_path is not None:
            log_file = open(log_path, "a", encoding="utf-8")
            log_file.write("$ " + " ".join(cmd) + "\n")
            log_file.flush()
        if log_callback is not None:
            log_callback("$ " + " ".join(cmd))

        process = subprocess.Popen(
            cmd,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if process.stdout is not None:
            for line in process.stdout:
                stripped = line.rstrip("\n")
                output_lines.append(stripped)
                if log_file is not None:
                    log_file.write(line)
                    log_file.flush()
                if log_callback is not None:
                    log_callback(stripped)
        returncode = process.wait()
    finally:
        if log_file is not None:
            log_file.close()

    output = "\n".join(output_lines)
    if output:
        output += "\n"
    return output, returncode
