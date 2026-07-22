"""Compile portable build profiles into normalized, host-independent requests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from termin.project_build.build_context import BuildContext, create_build_context
from termin.project_build.profiles import (
    AndroidTarget,
    BuildProfile,
    DesktopTarget,
    ProfileBuildError,
    ProfileDiagnostic,
    QuestOpenXRTarget,
    resolve_project_path,
)
from termin.project_build.toolchains import ToolchainContext


@dataclass(frozen=True)
class ProfileBuildRequest:
    name: str
    target: str
    target_os: str | None
    target_arch: str | None
    context: BuildContext
    scenes: tuple[Path, ...]
    modules: tuple[str, ...]
    resource_includes: tuple[str, ...]
    shader_compiler: Path | None
    fxc: Path | None
    default_shader_language: str
    runtime_backends: tuple[str, ...]
    sdk_root: Path | None
    python_package_policy: str
    python_requirements: tuple[str, ...]
    termin_root: Path | None
    build_script: Path | None
    gradle: Path | None
    abi: str | None
    platform: str | None
    toolchain: ToolchainContext


def compile_profile_build_request(
    profile: BuildProfile,
    toolchain: ToolchainContext | None = None,
) -> ProfileBuildRequest:
    """Compile a typed profile without probing local tool availability."""

    local = toolchain or ToolchainContext()
    output_dir = resolve_project_path(
        profile.project_root,
        profile.output_dir or Path("dist") / profile.name,
    )
    entry_scene = resolve_project_path(profile.project_root, profile.content.entry_scene)
    scenes = tuple(
        resolve_project_path(profile.project_root, scene)
        for scene in profile.content.scenes
    )

    target = profile.target
    if isinstance(target, DesktopTarget):
        target_options: dict[str, object] = {
            "desktop": {"os": target.os, "arch": target.arch}
        }
        target_os = target.os
        target_arch = target.arch
        runtime_backends = target.backends
        python_package_policy = target.python_package_policy
        abi = None
        platform = None
        build_script = None
    elif isinstance(target, AndroidTarget):
        target_options = {
            "android": {"abi": target.abi, "ndk_api": target.ndk_api}
        }
        target_os = "android"
        target_arch = target.abi
        runtime_backends = ("vulkan",)
        python_package_policy = "minimal_strict"
        abi = target.abi
        platform = f"android-{target.ndk_api}"
        build_script = local.android_build_script
    elif isinstance(target, QuestOpenXRTarget):
        target_options = {
            "quest_openxr": {"abi": target.abi, "ndk_api": target.ndk_api}
        }
        target_os = "android"
        target_arch = target.abi
        runtime_backends = ("vulkan",)
        python_package_policy = "minimal_strict"
        abi = target.abi
        platform = f"android-{target.ndk_api}"
        build_script = local.quest_openxr_build_script
    else:
        raise AssertionError(f"Unhandled typed build target: {type(target).__name__}")

    context = create_build_context(
        project_root=profile.project_root,
        entry_scene=entry_scene,
        scenes=scenes,
        target=target.kind,
        output_dir=output_dir,
        configuration=profile.configuration,
        resource_policy=profile.content.resource_policy,
        target_options=target_options,
    )
    return ProfileBuildRequest(
        name=profile.name,
        target=target.kind,
        target_os=target_os,
        target_arch=target_arch,
        context=context,
        scenes=scenes,
        modules=profile.content.modules,
        resource_includes=profile.content.resource_includes,
        shader_compiler=local.shader_compiler,
        fxc=local.fxc,
        default_shader_language="slang",
        runtime_backends=runtime_backends,
        sdk_root=local.sdk_root if isinstance(target, DesktopTarget) else None,
        python_package_policy=python_package_policy,
        python_requirements=profile.content.python_requirements,
        termin_root=local.termin_root if not isinstance(target, DesktopTarget) else None,
        build_script=build_script,
        gradle=local.gradle if not isinstance(target, DesktopTarget) else None,
        abi=abi,
        platform=platform,
        toolchain=local,
    )


def validate_resolved_profile_request(request: ProfileBuildRequest) -> None:
    """Validate project-owned roots without probing SDK/compiler capabilities."""

    from termin.project_build.target_preflight import (
        TargetPreflightError,
        preflight_project_build_context,
    )

    scene_diagnostics: list[ProfileDiagnostic] = []
    for index, scene in enumerate(request.scenes):
        path = f"profiles.{request.name}.content.scenes[{index}]"
        label = "Entry scene" if scene == request.context.entry_scene else "Selected scene"
        if not scene.exists():
            scene_diagnostics.append(
                ProfileDiagnostic(
                    code="project.resolution",
                    path=path,
                    message=f"{label} does not exist: {scene}",
                )
            )
        elif not scene.is_file():
            scene_diagnostics.append(
                ProfileDiagnostic(
                    code="project.resolution",
                    path=path,
                    message=f"{label} is not a file: {scene}",
                )
            )
    if scene_diagnostics:
        raise ProfileBuildError(diagnostics=tuple(scene_diagnostics))

    try:
        preflight_project_build_context(request.context, _target_display_name(request.target))
    except TargetPreflightError as exc:
        raise ProfileBuildError(
            diagnostics=tuple(
                ProfileDiagnostic(
                    code="project.resolution",
                    path=diagnostic.path,
                    message=diagnostic.message,
                )
                for diagnostic in exc.diagnostics
            )
        ) from exc

    unsupported: list[ProfileDiagnostic] = []
    if request.modules and request.target != "desktop":
        unsupported.append(
            ProfileDiagnostic(
                code="profile.feature_pending",
                path=f"profiles.{request.name}.content.modules",
                message="selected project modules are currently supported only for desktop bundles",
            )
        )
    if request.resource_includes:
        unsupported.append(
            ProfileDiagnostic(
                code="profile.feature_pending",
                path=f"profiles.{request.name}.content.resources.include",
                message="explicit dynamic resource roots are not implemented yet",
            )
        )
    if request.target != "desktop" and request.python_requirements:
        unsupported.append(
            ProfileDiagnostic(
                code="profile.feature_pending",
                path=f"profiles.{request.name}.content.python.requirements",
                message="target-specific Python requirements are currently implemented only for desktop",
            )
        )
    if request.target in ("android", "quest_openxr") and request.context.configuration != "debug":
        unsupported.append(
            ProfileDiagnostic(
                code="profile.feature_pending",
                path=f"profiles.{request.name}.configuration",
                message=(
                    "Android-family configuration currently emits only the debug Gradle "
                    "variant; select debug until variant mapping is implemented"
                ),
            )
        )
    if unsupported:
        raise ProfileBuildError(diagnostics=tuple(unsupported))


def _target_display_name(target: str) -> str:
    if target == "desktop":
        return "Desktop"
    if target == "android":
        return "Android"
    if target == "quest_openxr":
        return "Quest/OpenXR"
    return target
