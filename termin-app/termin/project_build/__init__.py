"""Build helpers for deployable Termin runtime packages."""

from termin.project_build.android_build import AndroidBuildResult, build_android_project
from termin.project_build.desktop_build import DesktopBuildResult, build_desktop_project
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
    "DesktopBuildResult",
    "QuestOpenXRBuildResult",
    "QuestOpenXRDeployResult",
    "RuntimePackageExportDiagnostic",
    "RuntimePackageExportResult",
    "build_android_project",
    "build_desktop_project",
    "build_quest_openxr_project",
    "default_quest_openxr_apk_path",
    "default_quest_openxr_log_path",
    "export_runtime_package",
    "install_quest_openxr_apk",
    "launch_quest_openxr_app",
    "validate_runtime_package",
]
