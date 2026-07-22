"""Stable, editor-safe capability diagnostics for typed build profiles."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from termin.project_build.capabilities import (
    SDKCapabilities,
    SDKCapabilityError,
    load_sdk_capabilities,
)
from termin.project_build.profile_requests import (
    ProfileBuildRequest,
    compile_profile_build_request,
)
from termin.project_build.profiles import BuildProfile, ProfileDiagnostic
from termin.project_build.toolchains import ToolchainContext, create_local_toolchain_context


@dataclass(frozen=True)
class ToolchainCapabilityReport:
    """A deterministic report shared by CLI and editor consumers."""

    profile_name: str
    target: str
    context: ToolchainContext
    diagnostics: tuple[ProfileDiagnostic, ...]

    @property
    def buildable(self) -> bool:
        return not self.diagnostics

    def to_dict(self) -> dict[str, object]:
        return {
            "buildable": self.buildable,
            "context": self.context.to_dict(),
            "diagnostics": [
                {
                    "code": diagnostic.code,
                    "path": diagnostic.path,
                    "message": diagnostic.message,
                }
                for diagnostic in self.diagnostics
            ],
            "profile": self.profile_name,
            "target": self.target,
        }


def inspect_profile_capabilities(
    profile: BuildProfile,
    *,
    editor_settings: ToolchainContext | None = None,
    invocation_overrides: ToolchainContext | None = None,
    installation_defaults: ToolchainContext | None = None,
    environ: Mapping[str, str] | None = None,
    host_os: str | None = None,
) -> ToolchainCapabilityReport:
    """Resolve local providers and inspect a profile without mutating project data."""

    context = create_local_toolchain_context(
        editor_settings=editor_settings,
        invocation_overrides=invocation_overrides,
        installation_defaults=installation_defaults,
        environ=environ,
    )
    request = compile_profile_build_request(profile, context)
    return inspect_request_capabilities(request, host_os=host_os)


def inspect_request_capabilities(
    request: ProfileBuildRequest,
    *,
    host_os: str | None = None,
) -> ToolchainCapabilityReport:
    diagnostics: list[ProfileDiagnostic] = []
    context = request.toolchain

    _validate_file(
        context.shader_compiler,
        code="capability.shader_compiler",
        path="toolchain.shader_compiler",
        label="termin_shaderc executable",
        diagnostics=diagnostics,
    )

    capabilities = _load_capability_manifest(context, diagnostics)
    if request.target == "desktop":
        _validate_desktop(request, capabilities, host_os or _host_os(), diagnostics)
    elif request.target in ("android", "quest_openxr"):
        _validate_android_family(request, capabilities, diagnostics)
    else:
        diagnostics.append(
            ProfileDiagnostic(
                code="capability.target.unsupported",
                path="toolchain.target",
                message=f"No local capability validator exists for target '{request.target}'",
            )
        )

    return ToolchainCapabilityReport(
        profile_name=request.name,
        target=request.target,
        context=context,
        diagnostics=tuple(diagnostics),
    )


def _load_capability_manifest(
    context: ToolchainContext,
    diagnostics: list[ProfileDiagnostic],
) -> SDKCapabilities | None:
    if context.sdk_root is None:
        diagnostics.append(
            ProfileDiagnostic(
                code="capability.sdk.missing",
                path="toolchain.sdk_root",
                message="Termin SDK root was not found",
            )
        )
        return None
    if not context.sdk_root.is_dir():
        diagnostics.append(
            ProfileDiagnostic(
                code="capability.sdk.missing",
                path="toolchain.sdk_root",
                message=f"Termin SDK root does not exist: {context.sdk_root}",
            )
        )
        return None
    try:
        return load_sdk_capabilities(
            sdk_root=context.sdk_root,
            android_sdk_root=context.android_sdk_root,
        )
    except SDKCapabilityError as exc:
        diagnostics.append(
            ProfileDiagnostic(
                code="capability.sdk.invalid",
                path="toolchain.sdk_root",
                message=f"Termin SDK capability metadata is invalid: {exc}",
            )
        )
        return None


def _validate_desktop(
    request: ProfileBuildRequest,
    capabilities: SDKCapabilities | None,
    host_os: str,
    diagnostics: list[ProfileDiagnostic],
) -> None:
    if request.target_os != host_os:
        diagnostics.append(
            ProfileDiagnostic(
                code="capability.host_platform.mismatch",
                path="toolchain.host_platform",
                message=(
                    f"Profile '{request.name}' targets desktop {request.target_os}, but the "
                    f"local host is {host_os}; no cross-platform executor is configured"
                ),
            )
        )

    if "d3d11" in request.runtime_backends:
        _validate_file(
            request.toolchain.fxc,
            code="capability.fxc",
            path="toolchain.fxc",
            label="D3D11 FXC executable",
            diagnostics=diagnostics,
        )

    if capabilities is None or capabilities.sdk_root is None:
        return
    desktop = capabilities.desktop
    if desktop.os != request.target_os or desktop.arch != request.target_arch:
        diagnostics.append(
            ProfileDiagnostic(
                code="capability.sdk.target_mismatch",
                path="toolchain.sdk_root",
                message=(
                    f"Termin SDK targets {desktop.os or 'unknown'}/{desktop.arch or 'unknown'}, "
                    f"but profile '{request.name}' requests "
                    f"{request.target_os}/{request.target_arch}"
                ),
            )
        )
    if not desktop.player:
        diagnostics.append(
            ProfileDiagnostic(
                code="capability.sdk.player_missing",
                path="toolchain.sdk_root",
                message="Termin SDK does not provide the desktop player executable",
            )
        )
    if not desktop.native_libraries:
        diagnostics.append(
            ProfileDiagnostic(
                code="capability.sdk.runtime_missing",
                path="toolchain.sdk_root",
                message="Termin SDK does not provide desktop native runtime libraries",
            )
        )
    if not desktop.python_runtime:
        diagnostics.append(
            ProfileDiagnostic(
                code="capability.sdk.python_runtime_missing",
                path="toolchain.sdk_root",
                message="Termin SDK does not provide the bundled desktop Python runtime",
            )
        )


def _validate_android_family(
    request: ProfileBuildRequest,
    capabilities: SDKCapabilities | None,
    diagnostics: list[ProfileDiagnostic],
) -> None:
    _validate_directory(
        request.toolchain.termin_root,
        code="capability.termin_root",
        path="toolchain.termin_root",
        label="Termin build root",
        diagnostics=diagnostics,
    )
    _validate_directory(
        request.toolchain.android_sdk_root,
        code="capability.android_sdk",
        path="toolchain.android_sdk_root",
        label="Termin Android SDK root",
        diagnostics=diagnostics,
    )
    _validate_file(
        request.build_script,
        code="capability.build_script",
        path="toolchain.build_script",
        label=f"{_target_label(request.target)} build script",
        diagnostics=diagnostics,
    )
    _validate_file(
        request.gradle,
        code="capability.gradle",
        path="toolchain.gradle",
        label="Gradle executable",
        diagnostics=diagnostics,
    )

    if capabilities is None or request.abi is None:
        return
    if not capabilities.android.has_abi(request.abi):
        diagnostics.append(
            ProfileDiagnostic(
                code="capability.android_sdk.abi_mismatch",
                path="toolchain.android_sdk_root",
                message=(
                    f"Termin Android SDK does not provide ABI '{request.abi}' required by "
                    f"profile '{request.name}'"
                ),
            )
        )
    if request.target == "quest_openxr" and not capabilities.quest_openxr.supports_openxr(
        request.abi
    ):
        diagnostics.append(
            ProfileDiagnostic(
                code="capability.quest_openxr.mismatch",
                path="toolchain.android_sdk_root",
                message=(
                    f"Termin Android SDK does not provide complete Quest/OpenXR support for "
                    f"ABI '{request.abi}'"
                ),
            )
        )


def _validate_file(
    value: Path | None,
    *,
    code: str,
    path: str,
    label: str,
    diagnostics: list[ProfileDiagnostic],
) -> None:
    if value is None:
        diagnostics.append(ProfileDiagnostic(f"{code}.missing", path, f"{label} was not found"))
    elif not value.is_file():
        diagnostics.append(
            ProfileDiagnostic(f"{code}.invalid", path, f"{label} is not a file: {value}")
        )


def _validate_directory(
    value: Path | None,
    *,
    code: str,
    path: str,
    label: str,
    diagnostics: list[ProfileDiagnostic],
) -> None:
    if value is None:
        diagnostics.append(ProfileDiagnostic(f"{code}.missing", path, f"{label} was not found"))
    elif not value.is_dir():
        diagnostics.append(
            ProfileDiagnostic(f"{code}.invalid", path, f"{label} is not a directory: {value}")
        )


def _host_os() -> str:
    return "windows" if os.name == "nt" else "linux"


def _target_label(target: str) -> str:
    return "Quest/OpenXR" if target == "quest_openxr" else "Android"


__all__ = [
    "ToolchainCapabilityReport",
    "inspect_profile_capabilities",
    "inspect_request_capabilities",
]
