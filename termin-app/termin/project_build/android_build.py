"""Android project build wrapper."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from termin.project_build.common import preload_project_resources, read_project_name
from termin.project_build.runtime_package_exporter import (
    RuntimePackageExportDiagnostic,
    RuntimePackageExportResult,
    export_runtime_package,
)
from termin.project_build.runtime_package_validator import validate_runtime_package
from termin.project_build.target_build_common import read_log_tail
from termin.project_build.target_preflight import preflight_android_build


@dataclass
class AndroidBuildResult:
    dist_dir: Path
    package_result: RuntimePackageExportResult
    apk_path: Path
    log_path: Path
    application_id: str
    launch_activity: str
    diagnostics: list[RuntimePackageExportDiagnostic] = field(default_factory=list)


def build_android_project(
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
) -> AndroidBuildResult:
    project_root_path = Path(project_root).resolve()
    project_name = read_project_name(project_root_path)
    dist_dir = _resolve_dist_dir(project_root_path, project_name, output_dir)
    package_dir = dist_dir / "package"
    apk_dir = dist_dir / "apk"
    logs_dir = dist_dir / "logs"
    apk_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    preflight_result = preflight_android_build(
        termin_root=termin_root,
        build_script=build_script,
        gradle=gradle,
    )

    preload_project_resources(project_root_path, "[AndroidBuild]")

    package_result = export_runtime_package(
        project_root=project_root_path,
        entry_scene=entry_scene,
        output_dir=package_dir,
        shader_compiler=shader_compiler,
        default_shader_language=default_shader_language,
    )
    package_validation_diagnostics = validate_runtime_package(package_result.package_dir)

    application_id = _android_application_id_from_project_name(project_name)
    launch_activity = "org.termin.android.TerminActivity"
    log_path = logs_dir / "android-build.log"
    _run_android_build_script(
        build_script=preflight_result.build_script,
        package_dir=package_result.package_dir,
        log_path=log_path,
        gradle=preflight_result.gradle,
        abi=abi,
        platform=platform,
        application_id=application_id,
        app_label=project_name,
    )

    source_apk = (
        preflight_result.termin_root
        / "build"
        / "android-gradle"
        / "app"
        / "outputs"
        / "apk"
        / "debug"
        / "app-debug.apk"
    )
    if not source_apk.exists():
        raise FileNotFoundError(f"Android build did not produce APK: {source_apk}")

    apk_path = apk_dir / f"{project_name}-debug.apk"
    shutil.copy2(source_apk, apk_path)

    return AndroidBuildResult(
        dist_dir=dist_dir,
        package_result=package_result,
        apk_path=apk_path,
        log_path=log_path,
        application_id=application_id,
        launch_activity=launch_activity,
        diagnostics=[
            *preflight_result.diagnostics,
            *package_result.diagnostics,
            *package_validation_diagnostics,
        ],
    )


def _resolve_dist_dir(project_root: Path, project_name: str, output_dir: str | Path | None) -> Path:
    if output_dir is not None:
        return Path(output_dir).resolve()
    return (project_root / "dist" / "android" / project_name).resolve()


def _run_android_build_script(
    build_script: Path,
    package_dir: Path,
    log_path: Path,
    gradle: Path | None,
    abi: str,
    platform: str,
    application_id: str,
    app_label: str,
) -> None:
    cmd = [
        str(build_script),
        "--assets-dir",
        str(package_dir),
        "--abi",
        abi,
        "--platform",
        platform,
        "--application-id",
        application_id,
        "--app-label",
        app_label,
    ]
    if gradle is not None:
        cmd.extend(["--gradle", str(gradle)])

    result = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        check=False,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        result.stdout + result.stderr,
        encoding="utf-8",
    )
    if result.returncode != 0:
        log_tail = read_log_tail(log_path)
        raise RuntimeError(
            f"Android build failed with exit code {result.returncode}; see {log_path}\n{log_tail}"
        )


def _android_application_id_from_project_name(project_name: str) -> str:
    slug = project_name.strip().lower()
    slug = re.sub(r"[^a-z0-9_]+", ".", slug)
    slug = re.sub(r"\.+", ".", slug).strip(".")
    parts = []
    for part in slug.split("."):
        if part == "":
            continue
        if part[0].isdigit():
            parts.append(f"p{part}")
        else:
            parts.append(part)
    if not parts:
        parts = ["project"]
    return "org.termin.builds." + ".".join(parts)
