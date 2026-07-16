"""Build helpers for deployable Termin runtime packages.

The profile store is intentionally available without importing build backends.
The historical package-level backend API remains available through lazy exports.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from termin.project_build.profiles import (
    AndroidTarget,
    BUILD_PROFILE_SCHEMA_VERSION,
    BuildProfile,
    BuildProfileStore,
    DesktopTarget,
    ProfileContent,
    ProfileDiagnostic,
    ProfileBuildError,
    QuestOpenXRTarget,
    load_build_profile,
    resolve_project_path,
)
from termin.project_build.profile_requests import (
    ProfileBuildRequest,
    ToolchainContext,
    compile_profile_build_request,
    validate_resolved_profile_request,
)


_LAZY_EXPORTS = {
    "AndroidBuildResult": "termin.project_build.android_build",
    "build_android_project": "termin.project_build.android_build",
    "BuildContext": "termin.project_build.build_context",
    "create_build_context": "termin.project_build.build_context",
    "AndroidSDKCapabilities": "termin.project_build.capabilities",
    "DesktopSDKCapabilities": "termin.project_build.capabilities",
    "QuestOpenXRSDKCapabilities": "termin.project_build.capabilities",
    "SDKCapabilities": "termin.project_build.capabilities",
    "SDKToolCapabilities": "termin.project_build.capabilities",
    "load_sdk_capabilities": "termin.project_build.capabilities",
    "DesktopBuildResult": "termin.project_build.desktop_build",
    "build_desktop_project": "termin.project_build.desktop_build",
    "BuildDiagnostic": "termin.project_build.diagnostics",
    "DiagnosticLike": "termin.project_build.diagnostics",
    "ProjectBuildPipelineError": "termin.project_build.pipeline",
    "ProjectBuildPipelineResult": "termin.project_build.pipeline",
    "TargetPackageStepResult": "termin.project_build.pipeline",
    "TargetPreflightStepResult": "termin.project_build.pipeline",
    "run_project_build_pipeline": "termin.project_build.pipeline",
    "QuestOpenXRBuildResult": "termin.project_build.quest_openxr_build",
    "QuestOpenXRDeployResult": "termin.project_build.quest_openxr_build",
    "build_quest_openxr_project": "termin.project_build.quest_openxr_build",
    "default_quest_openxr_apk_path": "termin.project_build.quest_openxr_build",
    "default_quest_openxr_log_path": "termin.project_build.quest_openxr_build",
    "install_quest_openxr_apk": "termin.project_build.quest_openxr_build",
    "launch_quest_openxr_app": "termin.project_build.quest_openxr_build",
    "RuntimePackageExportDiagnostic": "termin.project_build.runtime_package_exporter",
    "RuntimePackageExportResult": "termin.project_build.runtime_package_exporter",
    "export_runtime_package": "termin.project_build.runtime_package_exporter",
    "validate_runtime_package": "termin.project_build.runtime_package_validator",
}


def __getattr__(name: str) -> Any:
    """Resolve the compatibility facade without eagerly loading build backends."""
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = import_module(module_name).__dict__[name]
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted((*globals(), *_LAZY_EXPORTS))


__all__ = [
    "AndroidBuildResult",
    "AndroidSDKCapabilities",
    "AndroidTarget",
    "BuildContext",
    "BuildDiagnostic",
    "BuildProfile",
    "BuildProfileStore",
    "BUILD_PROFILE_SCHEMA_VERSION",
    "DesktopBuildResult",
    "DesktopSDKCapabilities",
    "DesktopTarget",
    "DiagnosticLike",
    "ProfileBuildError",
    "ProfileBuildRequest",
    "ProfileContent",
    "ProfileDiagnostic",
    "ProjectBuildPipelineError",
    "ProjectBuildPipelineResult",
    "QuestOpenXRBuildResult",
    "QuestOpenXRDeployResult",
    "QuestOpenXRSDKCapabilities",
    "QuestOpenXRTarget",
    "RuntimePackageExportDiagnostic",
    "RuntimePackageExportResult",
    "SDKCapabilities",
    "SDKToolCapabilities",
    "TargetPackageStepResult",
    "TargetPreflightStepResult",
    "build_android_project",
    "build_desktop_project",
    "build_quest_openxr_project",
    "compile_profile_build_request",
    "create_build_context",
    "default_quest_openxr_apk_path",
    "default_quest_openxr_log_path",
    "export_runtime_package",
    "install_quest_openxr_apk",
    "launch_quest_openxr_app",
    "load_build_profile",
    "load_sdk_capabilities",
    "resolve_project_path",
    "run_project_build_pipeline",
    "ToolchainContext",
    "validate_runtime_package",
    "validate_resolved_profile_request",
]
