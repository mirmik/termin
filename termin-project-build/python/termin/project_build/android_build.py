"""Android project build wrapper."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from termin.project.settings import load_project_settings
from termin.project_build.android_apk_pipeline import (
    AndroidApkProduct,
    build_android_apk,
    prepare_android_apk_output,
)
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
from termin.project_build.target_preflight import AndroidPreflightResult, preflight_android_build


ANDROID_APK_PRODUCT = AndroidApkProduct(
    display_name="Android",
    gradle_build_dir="android-gradle",
    artifact_qualifier="",
    log_filename="android-build.log",
)


@dataclass
class AndroidBuildResult:
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


@dataclass
class _AndroidTargetPackagePayload:
    apk_path: Path
    log_path: Path
    application_id: str
    application_label: str
    version_code: int
    version_name: str
    launch_activity: str


def build_android_project(
    project_root: str | Path,
    entry_scene: str | Path,
    scenes: Iterable[str | Path] | None = None,
    output_dir: str | Path | None = None,
    sdk_root: str | Path | None = None,
    termin_root: str | Path | None = None,
    android_sdk_root: str | Path | None = None,
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
            sdk_root=sdk_root,
            android_sdk_root=android_sdk_root,
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
        application_label=target_payload.application_label,
        version_code=target_payload.version_code,
        version_name=target_payload.version_name,
        launch_activity=target_payload.launch_activity,
        diagnostics=pipeline_result.diagnostics,
    )


def _prepare_android_output(context: BuildContext) -> None:
    prepare_android_apk_output(context.dist_dir, context.logs_dir)


def _android_target_preflight(
    termin_root: str | Path | None,
    sdk_root: str | Path | None,
    android_sdk_root: str | Path | None,
    build_script: str | Path | None,
    gradle: str | Path | None,
    abi: str,
    platform: str,
) -> TargetPreflightStepResult[AndroidPreflightResult]:
    preflight_result = preflight_android_build(
        termin_root=termin_root,
        sdk_root=sdk_root,
        android_sdk_root=android_sdk_root,
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
    application = load_project_settings(context.project_root).application
    launch_activity = "org.termin.android.TerminActivity"
    apk_result = build_android_apk(
        product=ANDROID_APK_PRODUCT,
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
    )

    return TargetPackageStepResult(
        payload=_AndroidTargetPackagePayload(
            apk_path=apk_result.apk_path,
            log_path=apk_result.log_path,
            application_id=application.application_id,
            application_label=application.label,
            version_code=application.version_code,
            version_name=application.version_name,
            launch_activity=launch_activity,
        ),
    )
