"""CLI and target dispatch for typed Termin product build profiles."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Sequence

from termin.project_build.android_build import build_android_project
from termin.project_build.desktop_build import build_desktop_project
from termin.project_build.pipeline import ProjectBuildPipelineError
from termin.project_build.profile_requests import (
    ProfileBuildRequest,
    ToolchainContext,
    compile_profile_build_request,
    validate_resolved_profile_request,
)
from termin.project_build.profiles import (
    BuildProfile,
    BuildProfileStore,
    ProfileBuildError,
    ProfileDiagnostic,
    load_build_profile,
)
from termin.project_build.quest_openxr_build import build_quest_openxr_project


SUPPORTED_TARGETS = ("android", "desktop", "quest_openxr")
SUPPORTED_SHADER_TARGETS = ("vulkan", "opengl", "d3d11")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _create_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "build":
            return build_profile_from_args(args)
        if args.command == "profiles":
            return list_profiles_from_args(args)
        if args.command == "profile":
            return show_profile_from_args(args)
        if args.command == "resolve":
            return resolve_profile_from_args(args)
        if args.command == "desktop":
            return _build_desktop_from_args(args)
    except ProfileBuildError as exc:
        print(f"termin profile build: {exc}", file=sys.stderr)
        return exc.exit_code

    return 1


def build_profile_from_args(args: argparse.Namespace) -> int:
    profile = load_build_profile(
        project_root=args.project_root,
        profiles_path=args.profiles_path,
        profile_name=args.profile,
    )
    if args.target is not None and args.target != profile.target_kind:
        raise ProfileBuildError(
            f"profile '{profile.name}' target mismatch: C++ launcher selected "
            f"'{args.target}', profile file contains '{profile.target_kind}'"
        )
    request = compile_profile_build_request(
        profile,
        ToolchainContext(shader_compiler=args.shader_compiler),
    )
    if args.dry_run:
        _print_request_summary(request)
        print("Dry run: build execution skipped.")
        return 0
    validate_resolved_profile_request(request)
    _validate_request_capabilities(request)
    return execute_profile_build_request(request)


def list_profiles_from_args(args: argparse.Namespace) -> int:
    store = BuildProfileStore.load(args.project_root, args.profiles_path)
    print(f"Project: {store.project_root}")
    print(f"Profiles: {store.path}")
    names = store.profile_names()
    if not names:
        print("No build profiles defined.")
        return 0
    for name in names:
        print(f"{name} ({store.get_profile(name).target_kind})")
    return 0


def show_profile_from_args(args: argparse.Namespace) -> int:
    profile = load_build_profile(args.project_root, args.profiles_path, args.profile)
    request = compile_profile_build_request(profile)
    _print_request_summary(request)
    return 0


def resolve_profile_from_args(args: argparse.Namespace) -> int:
    profile = load_build_profile(args.project_root, args.profiles_path, args.profile)
    request = compile_profile_build_request(profile)
    destination = args.request_output.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(_request_summary(request), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, destination)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise ProfileBuildError(f"failed to write resolved profile request {destination}: {exc}") from exc
    return 0


def normalize_profile_build_request(
    profile: BuildProfile,
    shader_compiler: Path | None = None,
    toolchain: ToolchainContext | None = None,
) -> ProfileBuildRequest:
    """Compatibility name for the canonical pure profile request compiler."""

    if shader_compiler is not None and toolchain is not None:
        raise ValueError("pass either shader_compiler or toolchain, not both")
    local = toolchain or ToolchainContext(shader_compiler=shader_compiler)
    return compile_profile_build_request(profile, local)


def build_profile(
    profile: BuildProfile,
    shader_compiler: Path | None = None,
    toolchain: ToolchainContext | None = None,
) -> int:
    request = normalize_profile_build_request(
        profile,
        shader_compiler=shader_compiler,
        toolchain=toolchain,
    )
    validate_resolved_profile_request(request)
    _validate_request_capabilities(request)
    return execute_profile_build_request(request)


def execute_profile_build_request(request: ProfileBuildRequest) -> int:
    try:
        if request.target == "desktop":
            result = build_desktop_project(
                project_root=request.context.project_root,
                entry_scene=request.context.entry_scene,
                output_dir=request.context.dist_dir,
                shader_compiler=request.shader_compiler,
                default_shader_language=request.default_shader_language,
                shader_targets=request.shader_targets,
                sdk_root=request.sdk_root,
                configuration=request.context.configuration,
                resource_policy=request.context.resource_policy,
                python_package_policy=request.python_package_policy,
                python_requirements=request.python_requirements,
            )
            _print_desktop_result(result)
            return _exit_code_for_diagnostics(result.diagnostics)

        if request.target == "android":
            if request.abi is None or request.platform is None:
                raise AssertionError("typed Android request must contain ABI and NDK platform")
            result = build_android_project(
                project_root=request.context.project_root,
                entry_scene=request.context.entry_scene,
                output_dir=request.context.dist_dir,
                termin_root=request.termin_root,
                build_script=request.build_script,
                gradle=request.gradle,
                shader_compiler=request.shader_compiler,
                default_shader_language=request.default_shader_language,
                shader_targets=request.shader_targets,
                abi=request.abi,
                platform=request.platform,
                configuration=request.context.configuration,
                resource_policy=request.context.resource_policy,
            )
            _print_android_result(result)
            return _exit_code_for_diagnostics(result.diagnostics)

        if request.target == "quest_openxr":
            if request.abi is None or request.platform is None:
                raise AssertionError("typed Quest request must contain ABI and NDK platform")
            result = build_quest_openxr_project(
                project_root=request.context.project_root,
                entry_scene=request.context.entry_scene,
                output_dir=request.context.dist_dir,
                termin_root=request.termin_root,
                build_script=request.build_script,
                gradle=request.gradle,
                shader_compiler=request.shader_compiler,
                default_shader_language=request.default_shader_language,
                shader_targets=request.shader_targets,
                abi=request.abi,
                platform=request.platform,
                configuration=request.context.configuration,
                resource_policy=request.context.resource_policy,
            )
            _print_quest_openxr_result(result)
            return _exit_code_for_diagnostics(result.diagnostics)
    except ProjectBuildPipelineError as exc:
        _print_diagnostics(exc.diagnostics)
        return 1

    raise AssertionError(f"Unhandled typed build request target: {request.target}")


def _validate_request_capabilities(request: ProfileBuildRequest) -> None:
    if request.target == "desktop" and "d3d11" in request.shader_targets:
        if request.shader_compiler is None and not _d3d11_shader_compiler_available(request.sdk_root):
            raise ProfileBuildError(
                diagnostics=(
                    ProfileDiagnostic(
                        code="capability.shader_compiler",
                        path="toolchain.shader_compiler",
                        message=(
                            f"profile '{request.name}' requests runtime backend 'd3d11', but fxc "
                            "was not found; D3D11 shader artifacts require TERMIN_FXC, fxc in "
                            "PATH, or fxc under TERMIN_SDK/bin"
                        ),
                    ),
                )
            )
    host_os = "windows" if os.name == "nt" else "linux"
    if request.target == "desktop" and request.target_os != host_os:
        raise ProfileBuildError(
            diagnostics=(
                ProfileDiagnostic(
                    code="capability.host_platform",
                    path="toolchain.host_platform",
                    message=(
                        f"profile '{request.name}' targets desktop {request.target_os}, but this "
                        f"host is {host_os}; cross-platform desktop toolchain validation is not "
                        "implemented yet"
                    ),
                ),
            )
        )


def _d3d11_shader_compiler_available(sdk_root: Path | None) -> bool:
    explicit = os.environ.get("TERMIN_FXC")
    if explicit:
        return Path(explicit).is_file()
    if shutil.which("fxc") is not None:
        return True

    sdk_candidates = []
    if sdk_root is not None:
        sdk_candidates.append(sdk_root)
    env_sdk = os.environ.get("TERMIN_SDK")
    if env_sdk:
        sdk_candidates.append(Path(env_sdk))
    for sdk in sdk_candidates:
        if (sdk / "bin" / "fxc").is_file() or (sdk / "bin" / "fxc.exe").is_file():
            return True

    return os.name == "nt"


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Execute a resolved Termin build profile")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build a resolved project profile")
    build_parser.add_argument("--project-root", type=Path, required=True)
    build_parser.add_argument("--profiles-path", type=Path, required=True)
    build_parser.add_argument("--profile", required=True)
    build_parser.add_argument("--target", default=None)
    build_parser.add_argument("--shader-compiler", type=Path, default=None)
    build_parser.add_argument("--dry-run", action="store_true")

    profiles_parser = subparsers.add_parser("profiles", help="List typed project build profiles")
    _add_profile_document_args(profiles_parser)

    profile_parser = subparsers.add_parser("profile", help="Show one normalized build profile")
    _add_profile_document_args(profile_parser)
    profile_parser.add_argument("--profile", required=True)

    resolve_parser = subparsers.add_parser(
        "resolve",
        help=argparse.SUPPRESS,
    )
    _add_profile_document_args(resolve_parser)
    resolve_parser.add_argument("--profile", required=True)
    resolve_parser.add_argument("--request-output", type=Path, required=True)

    desktop_parser = subparsers.add_parser(
        "desktop",
        help="Build desktop project artifacts using the direct argument form",
    )
    desktop_parser.add_argument("--project-root", type=Path, required=True)
    desktop_parser.add_argument("--entry-scene", type=Path, required=True)
    desktop_parser.add_argument("--output-dir", type=Path, required=True)
    desktop_parser.add_argument("--shader-compiler", type=Path, default=None)
    desktop_parser.add_argument(
        "--shader-target",
        action="append",
        dest="shader_targets",
        choices=SUPPORTED_SHADER_TARGETS,
        default=None,
        help="Add a runtime backend/shader artifact target. Repeat for multiple targets.",
    )
    return parser


def _add_profile_document_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--profiles-path", type=Path, required=True)


def _build_desktop_from_args(args: argparse.Namespace) -> int:
    project_root = args.project_root.resolve()
    result = build_desktop_project(
        project_root=project_root,
        entry_scene=_resolve_direct_path(project_root, args.entry_scene),
        output_dir=_resolve_direct_path(project_root, args.output_dir),
        shader_compiler=args.shader_compiler,
        shader_targets=tuple(args.shader_targets) if args.shader_targets is not None else None,
    )
    _print_desktop_result(result)
    return _exit_code_for_diagnostics(result.diagnostics)


def _resolve_direct_path(project_root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _request_summary(request: ProfileBuildRequest) -> dict[str, object]:
    return {
        "backends": list(request.shader_targets),
        "entry_scene": str(request.context.entry_scene),
        "modules": list(request.modules),
        "output_dir": str(request.context.dist_dir),
        "profile": request.name,
        "scenes": [str(scene) for scene in request.scenes],
        "target": request.target,
        "target_arch": request.target_arch,
        "target_os": request.target_os,
    }


def _print_request_summary(request: ProfileBuildRequest) -> None:
    summary = _request_summary(request)
    print(f"Profile: {summary['profile']}")
    print(f"Project: {request.context.project_root}")
    print(f"Target: {summary['target']}")
    if summary["target_os"] is not None:
        print(f"Target platform: {summary['target_os']}/{summary['target_arch']}")
    print(f"Entry scene: {summary['entry_scene']}")
    print(f"Output dir: {summary['output_dir']}")
    print(f"Runtime backends: {', '.join(request.shader_targets)}")


def _print_desktop_result(result: Any) -> None:
    print(f"Bundle: {result.dist_dir}")
    print(f"App manifest: {result.app_manifest_path}")
    print(f"Package: {result.package_result.package_dir}")
    print(f"Manifest: {result.package_result.manifest_path}")
    print(f"Resources: {len(_manifest_resources(result.package_result.manifest_path))}")
    _print_diagnostics(result.diagnostics)


def _print_android_result(result: Any) -> None:
    print(f"APK: {result.apk_path}")
    print(f"Package: {result.package_result.package_dir}")
    print(f"Manifest: {result.package_result.manifest_path}")
    print(f"Log: {result.log_path}")
    print(f"Application ID: {result.application_id}")
    print(f"Launch activity: {result.launch_activity}")
    print(f"Resources: {len(_manifest_resources(result.package_result.manifest_path))}")
    _print_diagnostics(result.diagnostics)


def _print_quest_openxr_result(result: Any) -> None:
    print(f"Quest/OpenXR APK: {result.apk_path}")
    print(f"Package: {result.package_result.package_dir}")
    print(f"Manifest: {result.package_result.manifest_path}")
    print(f"Log: {result.log_path}")
    print(f"Application ID: {result.application_id}")
    print(f"Launch activity: {result.launch_activity}")
    print(f"Resources: {len(_manifest_resources(result.package_result.manifest_path))}")
    _print_diagnostics(result.diagnostics)


def _manifest_resources(manifest_path: Path) -> list[object]:
    with manifest_path.open("r", encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict):
        raise ProfileBuildError(f"runtime package manifest must be a JSON object: {manifest_path}")
    resources = data.get("resources")
    return resources if isinstance(resources, list) else []


def _print_diagnostics(diagnostics: Sequence[Any]) -> None:
    for diagnostic in diagnostics:
        print(f"{diagnostic.level}: {diagnostic.path}: {diagnostic.message}")


def _exit_code_for_diagnostics(diagnostics: Sequence[Any]) -> int:
    return 1 if any(diagnostic.level == "error" for diagnostic in diagnostics) else 0


if __name__ == "__main__":
    sys.exit(main())
