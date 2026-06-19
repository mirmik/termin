"""Build helpers for deployable Termin runtime packages."""

from termin.project_build.android_build import AndroidBuildResult, build_android_project
from termin.project_build.build_context import BuildContext, create_build_context
from termin.project_build.capabilities import (
    AndroidSDKCapabilities,
    DesktopSDKCapabilities,
    QuestOpenXRSDKCapabilities,
    SDKCapabilities,
    SDKToolCapabilities,
    load_sdk_capabilities,
)
from termin.project_build.desktop_build import DesktopBuildResult, build_desktop_project
from termin.project_build.diagnostics import BuildDiagnostic, DiagnosticLike
from termin.project_build.pipeline import (
    ProjectBuildPipelineResult,
    TargetPackageStepResult,
    TargetPreflightStepResult,
    run_project_build_pipeline,
)
from termin.project_build.quest_openxr_build import (
    QuestOpenXRBuildResult,
    QuestOpenXRDeployResult,
    build_quest_openxr_project,
    default_quest_openxr_apk_path,
    default_quest_openxr_log_path,
    install_quest_openxr_apk,
    launch_quest_openxr_app,
)
from termin.project_build.runtime_package_exporter import (
    RuntimePackageExportDiagnostic,
    RuntimePackageExportResult,
    export_runtime_package,
)
from termin.project_build.runtime_package_validator import validate_runtime_package

__all__ = [
    "AndroidBuildResult",
    "AndroidSDKCapabilities",
    "BuildDiagnostic",
    "BuildContext",
    "DesktopBuildResult",
    "DesktopSDKCapabilities",
    "DiagnosticLike",
    "ProjectBuildPipelineResult",
    "QuestOpenXRBuildResult",
    "QuestOpenXRDeployResult",
    "QuestOpenXRSDKCapabilities",
    "RuntimePackageExportDiagnostic",
    "RuntimePackageExportResult",
    "SDKCapabilities",
    "SDKToolCapabilities",
    "TargetPackageStepResult",
    "TargetPreflightStepResult",
    "build_android_project",
    "create_build_context",
    "build_desktop_project",
    "build_quest_openxr_project",
    "default_quest_openxr_apk_path",
    "default_quest_openxr_log_path",
    "export_runtime_package",
    "install_quest_openxr_apk",
    "launch_quest_openxr_app",
    "load_sdk_capabilities",
    "validate_runtime_package",
    "run_project_build_pipeline",
]
