"""Quest/OpenXR project build and deployment helpers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from termin.project.settings import load_project_settings
from termin.project_build.android_deploy import (
    AndroidDeployResult,
    install_android_apk,
    launch_android_app,
)
from termin.project_build.android_apk_pipeline import (
    AndroidApkProduct,
    build_android_apk,
    prepare_android_apk_output,
)
from termin.project_build.build_context import BuildContext, create_build_context, resolve_build_dist_dir
from termin.project_build.common import read_project_name
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
from termin.project_build.target_preflight import QuestOpenXRPreflightResult, preflight_quest_openxr_build


QUEST_OPENXR_LAUNCH_ACTIVITY = "android.app.NativeActivity"
QUEST_OPENXR_APK_PRODUCT = AndroidApkProduct(
    display_name="Quest/OpenXR",
    gradle_build_dir="android-gradle-openxr",
    artifact_qualifier="quest-openxr",
    log_filename="quest-openxr-build.log",
)


@dataclass
class QuestOpenXRBuildResult:
    dist_dir: Path
    package_result: RuntimePackageExportResult
    apk_path: Path
    log_path: Path
    application_id: str
    application_label: str
    version_code: int
    version_name: str
    launch_activity: str
    diagnostics: list[DiagnosticLike] = field(default_factory=list)


QuestOpenXRDeployResult = AndroidDeployResult


@dataclass
class _QuestOpenXRTargetPackagePayload:
    apk_path: Path
    log_path: Path
    application_id: str
    application_label: str
    version_code: int
    version_name: str
    launch_activity: str


def build_quest_openxr_project(
    project_root: str | Path,
    entry_scene: str | Path,
    scenes: Iterable[str | Path] | None = None,
    output_dir: str | Path | None = None,
    sdk_root: str | Path | None = None,
    termin_root: str | Path | None = None,
    android_sdk_root: str | Path | None = None,
    android_home: str | Path | None = None,
    android_ndk_root: str | Path | None = None,
    java_home: str | Path | None = None,
    build_script: str | Path | None = None,
    gradle: str | Path | None = None,
    shader_compiler: str | Path | None = None,
    default_shader_language: str = "slang",
    shader_targets: Iterable[str] | None = None,
    abi: str = "arm64-v8a",
    platform: str = "android-26",
    log_callback: Callable[[str], None] | None = None,
    configuration: str = "dev",
    resource_policy: str = "strict",
) -> QuestOpenXRBuildResult:
    context = create_build_context(
        project_root=project_root,
        entry_scene=entry_scene,
        scenes=scenes,
        target="quest_openxr",
        output_dir=output_dir,
        configuration=configuration,
        resource_policy=resource_policy,
    )
    pipeline_result = run_project_build_pipeline(
        context=context,
        target_name="Quest/OpenXR",
        preload_log_tag="[QuestOpenXRBuild]",
        prepare_output=_prepare_quest_openxr_output,
        run_target_preflight=lambda: _quest_openxr_target_preflight(
            termin_root=termin_root,
            sdk_root=sdk_root,
            android_sdk_root=android_sdk_root,
            android_home=android_home,
            android_ndk_root=android_ndk_root,
            java_home=java_home,
            build_script=build_script,
            gradle=gradle,
            abi=abi,
            platform=platform,
        ),
        package_target=lambda build_context, package_result, preflight_result: _package_quest_openxr_target(
            build_context,
            package_result,
            preflight_result,
            abi=abi,
            platform=platform,
            log_callback=log_callback,
        ),
        shader_compiler=shader_compiler,
        default_shader_language=default_shader_language,
        shader_targets=shader_targets,
        export_package=export_runtime_package,
        validate_package=validate_runtime_package,
    )
    target_payload = pipeline_result.target_package_result.payload

    return QuestOpenXRBuildResult(
        dist_dir=context.dist_dir,
        package_result=pipeline_result.package_result,
        apk_path=target_payload.apk_path,
        log_path=target_payload.log_path,
        application_id=target_payload.application_id,
        application_label=target_payload.application_label,
        version_code=target_payload.version_code,
        version_name=target_payload.version_name,
        launch_activity=target_payload.launch_activity,
        diagnostics=pipeline_result.diagnostics,
    )


def _prepare_quest_openxr_output(context: BuildContext) -> None:
    prepare_android_apk_output(context.dist_dir, context.logs_dir)


def _quest_openxr_target_preflight(
    termin_root: str | Path | None,
    sdk_root: str | Path | None,
    android_sdk_root: str | Path | None,
    android_home: str | Path | None,
    android_ndk_root: str | Path | None,
    java_home: str | Path | None,
    build_script: str | Path | None,
    gradle: str | Path | None,
    abi: str,
    platform: str,
) -> TargetPreflightStepResult[QuestOpenXRPreflightResult]:
    preflight_result = preflight_quest_openxr_build(
        termin_root=termin_root,
        sdk_root=sdk_root,
        android_sdk_root=android_sdk_root,
        android_home=android_home,
        android_ndk_root=android_ndk_root,
        java_home=java_home,
        build_script=build_script,
        gradle=gradle,
        abi=abi,
        platform=platform,
    )
    return TargetPreflightStepResult(
        payload=preflight_result,
        diagnostics=preflight_result.diagnostics,
    )


def _package_quest_openxr_target(
    context: BuildContext,
    package_result: RuntimePackageExportResult,
    preflight_result: QuestOpenXRPreflightResult,
    abi: str,
    platform: str,
    log_callback: Callable[[str], None] | None,
) -> TargetPackageStepResult[_QuestOpenXRTargetPackagePayload]:
    application = load_project_settings(context.project_root).application
    apk_result = build_android_apk(
        product=QUEST_OPENXR_APK_PRODUCT,
        configuration=context.configuration,
        project_name=context.project_name,
        application_id=application.application_id,
        termin_root=preflight_result.termin_root,
        build_script=preflight_result.build_script,
        package_dir=package_result.package_dir,
        dist_dir=context.dist_dir,
        logs_dir=context.logs_dir,
        gradle=preflight_result.gradle,
        android_sdk_root=preflight_result.android_sdk_root,
        android_home=preflight_result.android_home,
        android_ndk_root=preflight_result.android_ndk_root,
        java_home=preflight_result.java_home,
        abi=abi,
        platform=platform,
        product_arguments=(
            "--application-id",
            application.application_id,
            "--app-label",
            application.label,
            "--version-code",
            str(application.version_code),
            "--version-name",
            application.version_name,
        ),
        log_callback=log_callback,
    )

    return TargetPackageStepResult(
        payload=_QuestOpenXRTargetPackagePayload(
            apk_path=apk_result.apk_path,
            log_path=apk_result.log_path,
            application_id=application.application_id,
            application_label=application.label,
            version_code=application.version_code,
            version_name=application.version_name,
            launch_activity=QUEST_OPENXR_LAUNCH_ACTIVITY,
        ),
    )


def install_quest_openxr_apk(
    apk_path: str | Path,
    adb: str | Path | None = None,
    log_path: str | Path | None = None,
    log_callback: Callable[[str], None] | None = None,
) -> QuestOpenXRDeployResult:
    return install_android_apk(apk_path, adb, log_path, log_callback)


def launch_quest_openxr_app(
    application_id: str,
    adb: str | Path | None = None,
    log_path: str | Path | None = None,
    log_callback: Callable[[str], None] | None = None,
) -> list[QuestOpenXRDeployResult]:
    return launch_android_app(
        application_id,
        adb,
        log_path,
        log_callback,
        wake_device=True,
    )


def default_quest_openxr_apk_path(
    project_root: str | Path,
    output_dir: str | Path | None = None,
) -> Path:
    project_root_path = Path(project_root).resolve()
    project_name = read_project_name(project_root_path)
    dist_dir = resolve_build_dist_dir(project_root_path, project_name, "quest_openxr", output_dir)
    return dist_dir / "apk" / f"{project_name}-quest-openxr-debug.apk"


def default_quest_openxr_log_path(
    project_root: str | Path,
    output_dir: str | Path | None = None,
) -> Path:
    project_root_path = Path(project_root).resolve()
    project_name = read_project_name(project_root_path)
    dist_dir = resolve_build_dist_dir(project_root_path, project_name, "quest_openxr", output_dir)
    return dist_dir / "logs" / "quest-openxr-deploy.log"
