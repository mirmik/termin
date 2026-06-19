"""Preflight checks for platform-specific project build wrappers."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from termin.project_build.build_context import BuildContext
from termin.project_build.capabilities import SDKCapabilities, SDKCapabilityError, load_sdk_capabilities
from termin.project_build.diagnostics import BuildDiagnostic, build_error, format_diagnostics
from termin.project_build.target_build_common import resolve_gradle, resolve_termin_root


ANDROID_BUILD_SCRIPT = "build-android-apk.sh"
QUEST_OPENXR_BUILD_SCRIPT = "build-quest-openxr-apk.sh"


class TargetPreflightError(RuntimeError):
    def __init__(self, target_name: str, diagnostics: list[BuildDiagnostic]) -> None:
        self.target_name = target_name
        self.diagnostics = diagnostics
        super().__init__(_format_diagnostics(target_name, diagnostics))


@dataclass
class ProjectBuildContextPreflightResult:
    context: BuildContext
    diagnostics: list[BuildDiagnostic] = field(default_factory=list)

    @property
    def project_root(self) -> Path:
        return self.context.project_root

    @property
    def entry_scene(self) -> Path:
        return self.context.entry_scene

    @property
    def output_dir(self) -> Path:
        return self.context.dist_dir


@dataclass
class DesktopPreflightResult:
    sdk_root: Path
    capabilities: SDKCapabilities
    diagnostics: list[BuildDiagnostic] = field(default_factory=list)


@dataclass
class AndroidPreflightResult:
    termin_root: Path
    build_script: Path
    android_sdk_root: Path
    gradle: Path | None
    capabilities: SDKCapabilities
    diagnostics: list[BuildDiagnostic] = field(default_factory=list)


@dataclass
class QuestOpenXRPreflightResult:
    termin_root: Path
    build_script: Path
    android_sdk_root: Path
    gradle: Path | None
    capabilities: SDKCapabilities
    diagnostics: list[BuildDiagnostic] = field(default_factory=list)


def preflight_project_build_context(
    context: BuildContext,
    target_name: str,
) -> ProjectBuildContextPreflightResult:
    diagnostics: list[BuildDiagnostic] = []

    _validate_project_root(context.project_root, diagnostics)
    _validate_entry_scene(context.project_root, context.entry_scene, diagnostics)
    _validate_output_dir(context.project_root, context.dist_dir, target_name, diagnostics)
    _raise_if_errors(target_name, diagnostics)

    return ProjectBuildContextPreflightResult(
        context=context,
        diagnostics=diagnostics,
    )


def preflight_desktop_build(
    sdk_root: str | Path | None,
) -> DesktopPreflightResult:
    target_name = "Desktop"
    diagnostics: list[BuildDiagnostic] = []
    capabilities = _load_capabilities(
        sdk_root=sdk_root,
        termin_root=None,
        target_name=target_name,
        diagnostics=diagnostics,
    )
    _raise_if_errors(target_name, diagnostics)

    if capabilities.sdk_root is None:
        diagnostics.append(
            build_error(
                "sdk",
                "Termin SDK root was not found. Set TERMIN_SDK or pass sdk_root explicitly.",
            )
        )
        _raise_if_errors(target_name, diagnostics)

    _validate_desktop_capabilities(capabilities, diagnostics)
    _raise_if_errors(target_name, diagnostics)

    resolved_sdk_root = capabilities.sdk_root
    if resolved_sdk_root is None:
        raise AssertionError("Desktop SDK root must be resolved after preflight")

    return DesktopPreflightResult(
        sdk_root=resolved_sdk_root,
        capabilities=capabilities,
        diagnostics=diagnostics,
    )


def preflight_android_build(
    termin_root: str | Path | None,
    build_script: str | Path | None,
    gradle: str | Path | None,
    abi: str = "arm64-v8a",
    platform: str = "android-26",
) -> AndroidPreflightResult:
    target_name = "Android"
    diagnostics: list[BuildDiagnostic] = []

    resolved_termin_root = _resolve_required_termin_root(
        termin_root,
        ANDROID_BUILD_SCRIPT,
        target_name,
        diagnostics,
    )
    _raise_if_errors(target_name, diagnostics)

    capabilities = _load_capabilities(
        sdk_root=None,
        termin_root=resolved_termin_root,
        target_name=target_name,
        diagnostics=diagnostics,
    )
    _raise_if_errors(target_name, diagnostics)

    resolved_build_script = _resolve_build_script(
        resolved_termin_root,
        build_script,
        ANDROID_BUILD_SCRIPT,
        target_name,
        diagnostics,
    )
    _validate_android_capabilities(
        capabilities,
        abi,
        platform,
        resolved_termin_root,
        target_name,
        diagnostics,
    )
    resolved_gradle = _resolve_checked_gradle(gradle, target_name, diagnostics)
    _raise_if_errors(target_name, diagnostics)

    return AndroidPreflightResult(
        termin_root=resolved_termin_root,
        build_script=resolved_build_script,
        android_sdk_root=capabilities.android.sdk_root,
        gradle=resolved_gradle,
        capabilities=capabilities,
        diagnostics=diagnostics,
    )


def preflight_quest_openxr_build(
    termin_root: str | Path | None,
    build_script: str | Path | None,
    gradle: str | Path | None,
    abi: str,
    platform: str,
) -> QuestOpenXRPreflightResult:
    target_name = "Quest/OpenXR"
    diagnostics: list[BuildDiagnostic] = []

    resolved_termin_root = _resolve_required_termin_root(
        termin_root,
        QUEST_OPENXR_BUILD_SCRIPT,
        target_name,
        diagnostics,
    )
    _raise_if_errors(target_name, diagnostics)

    capabilities = _load_capabilities(
        sdk_root=None,
        termin_root=resolved_termin_root,
        target_name=target_name,
        diagnostics=diagnostics,
    )
    _raise_if_errors(target_name, diagnostics)

    resolved_build_script = _resolve_build_script(
        resolved_termin_root,
        build_script,
        QUEST_OPENXR_BUILD_SCRIPT,
        target_name,
        diagnostics,
    )
    _validate_android_capabilities(
        capabilities,
        abi,
        platform,
        resolved_termin_root,
        target_name,
        diagnostics,
    )
    _raise_if_errors(target_name, diagnostics)

    _validate_quest_openxr_capabilities(
        capabilities,
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
        android_sdk_root=capabilities.android.sdk_root,
        gradle=resolved_gradle,
        capabilities=capabilities,
        diagnostics=diagnostics,
    )


def _validate_project_root(
    project_root: Path,
    diagnostics: list[BuildDiagnostic],
) -> None:
    if not project_root.exists():
        diagnostics.append(
            build_error(
                str(project_root),
                f"Project root does not exist: {project_root}",
            )
        )
        return

    if not project_root.is_dir():
        diagnostics.append(
            build_error(
                str(project_root),
                f"Project root is not a directory: {project_root}",
            )
        )


def _validate_entry_scene(
    project_root: Path,
    entry_scene: Path,
    diagnostics: list[BuildDiagnostic],
) -> None:
    if project_root.exists() and not _path_is_relative_to(entry_scene, project_root):
        diagnostics.append(
            build_error(
                str(entry_scene),
                f"Entry scene must stay inside project root: {entry_scene}",
            )
        )

    if not entry_scene.exists():
        diagnostics.append(
            build_error(
                str(entry_scene),
                f"Entry scene does not exist: {entry_scene}",
            )
        )
        return

    if not entry_scene.is_file():
        diagnostics.append(
            build_error(
                str(entry_scene),
                f"Entry scene is not a file: {entry_scene}",
            )
        )


def _validate_output_dir(
    project_root: Path,
    output_dir: Path,
    target_name: str,
    diagnostics: list[BuildDiagnostic],
) -> None:
    if output_dir == project_root:
        diagnostics.append(
            build_error(
                str(output_dir),
                f"Refusing to use project root as {target_name} build output: {output_dir}",
            )
        )
        return

    if _path_is_relative_to(output_dir, project_root):
        rel = output_dir.relative_to(project_root)
        if rel.parts and rel.parts[0] == "dist":
            return
        diagnostics.append(
            build_error(
                str(output_dir),
                f"Refusing to use project-internal {target_name} build output outside dist/: {output_dir}",
            )
        )
        return

    if not output_dir.exists():
        return

    if not output_dir.is_dir():
        diagnostics.append(
            build_error(
                str(output_dir),
                f"Build output exists and is not a directory: {output_dir}",
            )
        )
        return

    if any(output_dir.iterdir()):
        diagnostics.append(
            build_error(
                str(output_dir),
                "Refusing to use non-empty external build output directory: "
                f"{output_dir}. Use a project dist/... path or an empty directory.",
            )
        )


def _resolve_required_termin_root(
    termin_root: str | Path | None,
    marker_script_name: str,
    target_name: str,
    diagnostics: list[BuildDiagnostic],
) -> Path:
    try:
        return resolve_termin_root(
            termin_root,
            marker_script_name=marker_script_name,
            target_name=target_name,
        )
    except FileNotFoundError as exc:
        diagnostics.append(
            build_error(
                "termin_root",
                str(exc),
            )
        )
        return Path()


def _resolve_build_script(
    termin_root: Path,
    build_script: str | Path | None,
    default_script_name: str,
    target_name: str,
    diagnostics: list[BuildDiagnostic],
) -> Path:
    if build_script is not None:
        script = Path(build_script).expanduser().resolve()
    else:
        script = termin_root / default_script_name

    if not script.exists():
        diagnostics.append(
            build_error(
                str(script),
                f"{target_name} build script does not exist: {script}",
            )
        )
    return script


def _load_capabilities(
    sdk_root: str | Path | None,
    termin_root: Path | None,
    target_name: str,
    diagnostics: list[BuildDiagnostic],
) -> SDKCapabilities:
    try:
        return load_sdk_capabilities(
            sdk_root=sdk_root,
            termin_root=termin_root,
        )
    except SDKCapabilityError as exc:
        diagnostics.append(
            build_error(
                "sdk",
                f"{target_name} SDK capabilities could not be loaded: {exc}",
            )
        )
        return load_sdk_capabilities(
            sdk_root=None,
            termin_root=None,
            android_sdk_root=Path(),
        )


def _validate_desktop_capabilities(
    capabilities: SDKCapabilities,
    diagnostics: list[BuildDiagnostic],
) -> None:
    sdk_root = capabilities.sdk_root
    if sdk_root is None:
        return

    if not capabilities.desktop.player:
        diagnostics.append(
            build_error(
                str(sdk_root / "bin" / "termin_player"),
                f"termin_player executable was not found in SDK: {sdk_root / 'bin'}",
            )
        )

    if not capabilities.desktop.native_libraries:
        diagnostics.append(
            build_error(
                str(sdk_root / "lib"),
                f"No native libraries were found in SDK lib directory: {sdk_root / 'lib'}",
            )
        )

    if not capabilities.desktop.python_runtime:
        diagnostics.append(
            build_error(
                str(sdk_root / "lib" / "python"),
                f"Bundled Python stdlib was not found in SDK: {sdk_root / 'lib'}",
            )
        )


def _validate_android_capabilities(
    capabilities: SDKCapabilities,
    abi: str,
    platform: str,
    termin_root: Path,
    target_name: str,
    diagnostics: list[BuildDiagnostic],
) -> None:
    android_sdk_root = capabilities.android.sdk_root
    sdk_prefix = android_sdk_root / abi
    sdk_lib_dir = sdk_prefix / "lib"

    if not android_sdk_root.exists():
        diagnostics.append(
            build_error(
                str(android_sdk_root),
                "Termin Android SDK is not installed. "
                f"Build and install it first: {termin_root / 'build-sdk-android.sh'} "
                f"--abi {abi} --platform {platform}. "
                "Or set TERMIN_ANDROID_SDK_ROOT to another Android SDK root.",
            )
        )
        return

    if not capabilities.android.has_abi(abi):
        diagnostics.append(
            build_error(
                str(sdk_prefix),
                f"{target_name} SDK capabilities are missing the requested ABI. "
                f"Build and install it first: {termin_root / 'build-sdk-android.sh'} "
                f"--abi {abi} --platform {platform}. "
                "Or choose an ABI that exists in the Termin Android SDK.",
            )
        )
        return

    if not sdk_lib_dir.is_dir():
        diagnostics.append(
            build_error(
                str(sdk_lib_dir),
                f"{target_name} SDK ABI prefix is incomplete: lib directory is missing. "
                f"Rebuild and reinstall the Android SDK: {termin_root / 'build-sdk-android.sh'} "
                f"--abi {abi} --platform {platform}.",
            )
        )
        return


def _validate_quest_openxr_capabilities(
    capabilities: SDKCapabilities,
    abi: str,
    platform: str,
    termin_root: Path,
    diagnostics: list[BuildDiagnostic],
) -> None:
    openxr_config = capabilities.quest_openxr.openxr_config_path(abi)

    if not capabilities.quest_openxr.supports_openxr(abi):
        diagnostics.append(
            build_error(
                str(openxr_config),
                "Termin SDK capabilities report that OpenXR support is missing. "
                "Rebuild and reinstall the Android SDK with termin-openxr enabled: "
                f"{termin_root / 'build-sdk-android.sh'} --abi {abi} --platform {platform}.",
            )
        )


def _resolve_checked_gradle(
    gradle: str | Path | None,
    target_name: str,
    diagnostics: list[BuildDiagnostic],
) -> Path | None:
    resolved_gradle = resolve_gradle(gradle)
    env_gradle = os.environ.get("GRADLE_BIN")
    should_exist = gradle is not None or env_gradle is not None
    if should_exist and resolved_gradle is not None and not resolved_gradle.exists():
        diagnostics.append(
            build_error(
                str(resolved_gradle),
                f"{target_name} Gradle executable does not exist: {resolved_gradle}",
            )
        )
    return resolved_gradle


def _raise_if_errors(
    target_name: str,
    diagnostics: list[BuildDiagnostic],
) -> None:
    if any(diagnostic.level == "error" for diagnostic in diagnostics):
        raise TargetPreflightError(target_name, diagnostics)


def _path_is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
    except ValueError:
        return False
    return True


def _format_diagnostics(
    target_name: str,
    diagnostics: list[BuildDiagnostic],
) -> str:
    return format_diagnostics(f"{target_name} build preflight failed:", diagnostics)
