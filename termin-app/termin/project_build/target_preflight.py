"""Preflight checks for platform-specific project build wrappers."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from termin.project_build.runtime_package_exporter import RuntimePackageExportDiagnostic
from termin.project_build.target_build_common import resolve_gradle, resolve_termin_root


QUEST_OPENXR_BUILD_SCRIPT = "build-quest-openxr-apk.sh"


class TargetPreflightError(RuntimeError):
    def __init__(self, target_name: str, diagnostics: list[RuntimePackageExportDiagnostic]) -> None:
        self.target_name = target_name
        self.diagnostics = diagnostics
        super().__init__(_format_diagnostics(target_name, diagnostics))


@dataclass
class QuestOpenXRPreflightResult:
    termin_root: Path
    build_script: Path
    android_sdk_root: Path
    gradle: Path | None
    diagnostics: list[RuntimePackageExportDiagnostic] = field(default_factory=list)


def preflight_quest_openxr_build(
    termin_root: str | Path | None,
    build_script: str | Path | None,
    gradle: str | Path | None,
    abi: str,
    platform: str,
) -> QuestOpenXRPreflightResult:
    target_name = "Quest/OpenXR"
    diagnostics: list[RuntimePackageExportDiagnostic] = []

    resolved_termin_root = _resolve_required_termin_root(
        termin_root,
        target_name,
        diagnostics,
    )
    _raise_if_errors(target_name, diagnostics)

    resolved_build_script = _resolve_build_script(
        resolved_termin_root,
        build_script,
        target_name,
        diagnostics,
    )
    android_sdk_root = _resolve_termin_android_sdk_root(resolved_termin_root)
    _validate_termin_android_sdk(
        android_sdk_root,
        abi,
        platform,
        resolved_termin_root,
        diagnostics,
    )
    resolved_gradle = _resolve_checked_gradle(gradle, target_name, diagnostics)
    _raise_if_errors(target_name, diagnostics)

    return QuestOpenXRPreflightResult(
        termin_root=resolved_termin_root,
        build_script=resolved_build_script,
        android_sdk_root=android_sdk_root,
        gradle=resolved_gradle,
        diagnostics=diagnostics,
    )


def _resolve_required_termin_root(
    termin_root: str | Path | None,
    target_name: str,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> Path:
    try:
        return resolve_termin_root(
            termin_root,
            marker_script_name=QUEST_OPENXR_BUILD_SCRIPT,
            target_name=target_name,
        )
    except FileNotFoundError as exc:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "termin_root",
                str(exc),
            )
        )
        return Path()


def _resolve_build_script(
    termin_root: Path,
    build_script: str | Path | None,
    target_name: str,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> Path:
    if build_script is not None:
        script = Path(build_script).expanduser().resolve()
    else:
        script = termin_root / QUEST_OPENXR_BUILD_SCRIPT

    if not script.exists():
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                str(script),
                f"{target_name} build script does not exist: {script}",
            )
        )
    return script


def _resolve_termin_android_sdk_root(termin_root: Path) -> Path:
    env_sdk_root = os.environ.get("TERMIN_ANDROID_SDK_ROOT")
    if env_sdk_root:
        return Path(env_sdk_root).expanduser().resolve()
    return (termin_root / "sdk" / "android").resolve()


def _validate_termin_android_sdk(
    android_sdk_root: Path,
    abi: str,
    platform: str,
    termin_root: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    sdk_prefix = android_sdk_root / abi
    sdk_lib_dir = sdk_prefix / "lib"
    openxr_config = sdk_lib_dir / "cmake" / "termin_openxr" / "termin_openxrConfig.cmake"

    if not android_sdk_root.exists():
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                str(android_sdk_root),
                "Termin Android SDK is not installed. "
                f"Build and install it first: {termin_root / 'build-sdk-android.sh'} "
                f"--abi {abi} --platform {platform}. "
                "Or set TERMIN_ANDROID_SDK_ROOT to another Android SDK root.",
            )
        )
        return

    if not sdk_prefix.exists():
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                str(sdk_prefix),
                "Termin Android SDK is missing the requested ABI. "
                f"Build and install it first: {termin_root / 'build-sdk-android.sh'} "
                f"--abi {abi} --platform {platform}. "
                "Or choose an ABI that exists in the Termin Android SDK.",
            )
        )
        return

    if not sdk_lib_dir.is_dir():
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                str(sdk_lib_dir),
                "Termin Android SDK ABI prefix is incomplete: lib directory is missing. "
                f"Rebuild and reinstall the Android SDK: {termin_root / 'build-sdk-android.sh'} "
                f"--abi {abi} --platform {platform}.",
            )
        )
        return

    if not openxr_config.is_file():
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                str(openxr_config),
                "Termin Android SDK is installed, but OpenXR support is missing. "
                "Rebuild and reinstall the Android SDK with termin-openxr enabled: "
                f"{termin_root / 'build-sdk-android.sh'} --abi {abi} --platform {platform}.",
            )
        )


def _resolve_checked_gradle(
    gradle: str | Path | None,
    target_name: str,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> Path | None:
    resolved_gradle = resolve_gradle(gradle)
    env_gradle = os.environ.get("GRADLE_BIN")
    should_exist = gradle is not None or env_gradle is not None
    if should_exist and resolved_gradle is not None and not resolved_gradle.exists():
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                str(resolved_gradle),
                f"{target_name} Gradle executable does not exist: {resolved_gradle}",
            )
        )
    return resolved_gradle


def _raise_if_errors(
    target_name: str,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    if any(diagnostic.level == "error" for diagnostic in diagnostics):
        raise TargetPreflightError(target_name, diagnostics)


def _format_diagnostics(
    target_name: str,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> str:
    lines = [f"{target_name} build preflight failed:"]
    for diagnostic in diagnostics:
        lines.append(f"- {diagnostic.level}: {diagnostic.path}: {diagnostic.message}")
    return "\n".join(lines)
