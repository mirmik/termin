"""Android project build wrapper."""

from __future__ import annotations

from collections.abc import Iterable
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from termin.project_build.build_context import BuildContext, create_build_context
from termin.project_build.diagnostics import DiagnosticLike
from termin.project_build.pipeline import (
    TargetPackageStepResult,
    TargetPreflightStepResult,
    run_project_build_pipeline,
)
from termin.project_build.runtime_package_exporter import (
    RuntimePackageExportResult,
    export_runtime_package,
)
from termin.project_build.runtime_package_validator import validate_runtime_package
from termin.project_build.target_build_common import read_log_tail
from termin.project_build.target_preflight import AndroidPreflightResult, preflight_android_build


@dataclass
class AndroidBuildResult:
    dist_dir: Path
    package_result: RuntimePackageExportResult
    apk_path: Path
    log_path: Path
    application_id: str
    launch_activity: str
    diagnostics: list[DiagnosticLike] = field(default_factory=list)


@dataclass
class _AndroidTargetPackagePayload:
    apk_path: Path
    log_path: Path
    application_id: str
    launch_activity: str


def build_android_project(
    project_root: str | Path,
    entry_scene: str | Path,
    scenes: Iterable[str | Path] | None = None,
    output_dir: str | Path | None = None,
    termin_root: str | Path | None = None,
    build_script: str | Path | None = None,
    gradle: str | Path | None = None,
    shader_compiler: str | Path | None = None,
    default_shader_language: str = "slang",
    shader_targets: Iterable[str] | None = None,
    abi: str = "arm64-v8a",
    platform: str = "android-26",
    configuration: str = "dev",
    resource_policy: str = "strict",
) -> AndroidBuildResult:
    context = create_build_context(
        project_root=project_root,
        entry_scene=entry_scene,
        scenes=scenes,
        target="android",
        output_dir=output_dir,
        configuration=configuration,
        resource_policy=resource_policy,
    )
    pipeline_result = run_project_build_pipeline(
        context=context,
        target_name="Android",
        preload_log_tag="[AndroidBuild]",
        prepare_output=_prepare_android_output,
        run_target_preflight=lambda: _android_target_preflight(
            termin_root=termin_root,
            build_script=build_script,
            gradle=gradle,
            abi=abi,
            platform=platform,
        ),
        package_target=lambda build_context, package_result, preflight_result: _package_android_target(
            build_context,
            package_result,
            preflight_result,
            abi=abi,
            platform=platform,
        ),
        shader_compiler=shader_compiler,
        default_shader_language=default_shader_language,
        shader_targets=shader_targets,
        export_package=export_runtime_package,
        validate_package=validate_runtime_package,
    )
    target_payload = pipeline_result.target_package_result.payload

    return AndroidBuildResult(
        dist_dir=context.dist_dir,
        package_result=pipeline_result.package_result,
        apk_path=target_payload.apk_path,
        log_path=target_payload.log_path,
        application_id=target_payload.application_id,
        launch_activity=target_payload.launch_activity,
        diagnostics=pipeline_result.diagnostics,
    )


def _prepare_android_output(context: BuildContext) -> None:
    (context.dist_dir / "apk").mkdir(parents=True, exist_ok=True)
    context.logs_dir.mkdir(parents=True, exist_ok=True)


def _android_target_preflight(
    termin_root: str | Path | None,
    build_script: str | Path | None,
    gradle: str | Path | None,
    abi: str,
    platform: str,
) -> TargetPreflightStepResult[AndroidPreflightResult]:
    preflight_result = preflight_android_build(
        termin_root=termin_root,
        build_script=build_script,
        gradle=gradle,
        abi=abi,
        platform=platform,
    )
    return TargetPreflightStepResult(
        payload=preflight_result,
        diagnostics=preflight_result.diagnostics,
    )


def _package_android_target(
    context: BuildContext,
    package_result: RuntimePackageExportResult,
    preflight_result: AndroidPreflightResult,
    abi: str,
    platform: str,
) -> TargetPackageStepResult[_AndroidTargetPackagePayload]:
    application_id = _android_application_id_from_project_name(context.project_name)
    launch_activity = "org.termin.android.TerminActivity"
    log_path = context.logs_dir / "android-build.log"
    _run_android_build_script(
        build_script=preflight_result.build_script,
        package_dir=package_result.package_dir,
        log_path=log_path,
        gradle=preflight_result.gradle,
        android_sdk_root=preflight_result.android_sdk_root,
        abi=abi,
        platform=platform,
        application_id=application_id,
        app_label=context.project_name,
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

    apk_path = context.dist_dir / "apk" / f"{context.project_name}-debug.apk"
    shutil.copy2(source_apk, apk_path)

    return TargetPackageStepResult(
        payload=_AndroidTargetPackagePayload(
            apk_path=apk_path,
            log_path=log_path,
            application_id=application_id,
            launch_activity=launch_activity,
        ),
    )


def _run_android_build_script(
    build_script: Path,
    package_dir: Path,
    log_path: Path,
    gradle: Path | None,
    android_sdk_root: Path,
    abi: str,
    platform: str,
    application_id: str,
    app_label: str,
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
