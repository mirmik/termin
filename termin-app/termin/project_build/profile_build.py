"""Profile build backend used by the C++ termin_builder entry point."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from termin.project_build import build_android_project, build_desktop_project, build_quest_openxr_project
from termin.project_build.build_context import BuildContext, create_build_context
from termin.project_build.pipeline import ProjectBuildPipelineError
from termin.project_build.target_preflight import TargetPreflightError, preflight_project_build_context


SUPPORTED_TARGETS = ("android", "desktop", "quest_openxr")
BUILD_PROFILE_SCHEMA_VERSION = 1
SUPPORTED_CONFIGURATIONS = ("dev", "debug", "release")
SUPPORTED_RESOURCE_POLICIES = ("dev", "dev_smoke", "strict")
SUPPORTED_SHADER_TARGETS = ("vulkan", "opengl", "d3d11")
COMMON_PROFILE_KEYS = {
    "target",
    "configuration",
    "entry_scene",
    "output_dir",
    "resource_policy",
    "shader_compiler",
    "default_shader_language",
    "shader_targets",
    "termin_root",
    "build_script",
    "python",
    "runtime",
}
TARGET_OPTION_BLOCKS = {
    "android": {"android"},
    "desktop": {"desktop"},
    "quest_openxr": {"android", "openxr"},
}


class ProfileBuildError(RuntimeError):
    def __init__(self, message: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class UnsupportedBuildTargetError(ProfileBuildError):
    def __init__(self, target: str) -> None:
        supported = ", ".join(SUPPORTED_TARGETS)
        super().__init__(
            f"unsupported build target '{target}'. Supported targets: {supported}",
            exit_code=3,
        )


@dataclass(frozen=True)
class BuildProfile:
    name: str
    project_root: Path
    target: str
    entry_scene: Path
    output_dir: Path
    data: Mapping[str, Any]


@dataclass(frozen=True)
class ProfileBuildRequest:
    name: str
    target: str
    context: BuildContext
    shader_compiler: Path | None
    default_shader_language: str
    shader_targets: tuple[str, ...] | None
    sdk_root: Path | None
    termin_root: Path | None
    build_script: Path | None
    gradle: Path | None
    abi: str
    platform: str


def main(argv: Sequence[str] | None = None) -> int:
    parser = _create_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "build":
            return build_profile_from_args(args)
        if args.command == "desktop":
            return _build_legacy_desktop(args)
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
    if args.target is not None and args.target != profile.target:
        raise ProfileBuildError(
            f"profile '{profile.name}' target mismatch: C++ launcher selected "
            f"'{args.target}', profile file contains '{profile.target}'"
        )
    return build_profile(profile, shader_compiler=args.shader_compiler)


def load_build_profile(project_root: Path, profiles_path: Path, profile_name: str) -> BuildProfile:
    project_root = project_root.resolve()
    profiles_path = profiles_path.resolve()
    root = _read_json_object(profiles_path)
    _validate_schema_version(root, context=str(profiles_path))
    profiles = _required_object(root, "profiles", context=str(profiles_path))
    raw_profile = _required_object(profiles, profile_name, context="profiles")

    target = _required_string(raw_profile, "target", context=f"profile '{profile_name}'")
    entry_scene = _resolve_project_path(
        project_root,
        _required_string(raw_profile, "entry_scene", context=f"profile '{profile_name}'"),
    )
    output_dir = _resolve_project_path(
        project_root,
        _required_string(raw_profile, "output_dir", context=f"profile '{profile_name}'"),
    )

    return BuildProfile(
        name=profile_name,
        project_root=project_root,
        target=target,
        entry_scene=entry_scene,
        output_dir=output_dir,
        data=raw_profile,
    )


def build_profile(profile: BuildProfile, shader_compiler: Path | None = None) -> int:
    request = normalize_profile_build_request(profile, shader_compiler=shader_compiler)

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
            )
            _print_desktop_result(result)
            return _exit_code_for_diagnostics(result.diagnostics)

        if request.target == "android":
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

    raise UnsupportedBuildTargetError(request.target)


def normalize_profile_build_request(
    profile: BuildProfile,
    shader_compiler: Path | None = None,
) -> ProfileBuildRequest:
    _validate_supported_target(profile.target)
    _validate_target_option_blocks(profile)

    target_options = _target_options(profile)
    configuration = _profile_string_choice(
        profile,
        "configuration",
        "dev",
        SUPPORTED_CONFIGURATIONS,
    )
    resource_policy = _profile_string_choice(
        profile,
        "resource_policy",
        "strict",
        SUPPORTED_RESOURCE_POLICIES,
    )
    context = create_build_context(
        project_root=profile.project_root,
        entry_scene=profile.entry_scene,
        target=profile.target,
        output_dir=profile.output_dir,
        configuration=configuration,
        resource_policy=resource_policy,
        target_options=target_options,
    )
    try:
        preflight_project_build_context(context, _target_display_name(profile.target))
    except TargetPreflightError as exc:
        raise ProfileBuildError(f"profile '{profile.name}' failed build preflight: {exc}") from exc

    android = _optional_object(profile.data, "android", context=f"profile '{profile.name}'")
    openxr = _optional_object(profile.data, "openxr", context=f"profile '{profile.name}'")
    shader_compiler_path = _profile_path(profile, "shader_compiler", shader_compiler)
    shader_targets = _profile_shader_targets(profile)
    sdk_root = _desktop_path(profile, "sdk_root") if profile.target == "desktop" else None
    _validate_shader_target_tools(profile, shader_targets, shader_compiler_path, sdk_root)

    return ProfileBuildRequest(
        name=profile.name,
        target=profile.target,
        context=context,
        shader_compiler=shader_compiler_path,
        default_shader_language=_profile_string(profile, "default_shader_language", "slang"),
        shader_targets=shader_targets,
        sdk_root=sdk_root,
        termin_root=_target_termin_root(profile, android),
        build_script=_target_build_script(profile, android, openxr),
        gradle=_android_path(profile, android, "gradle")
        if profile.target in ("android", "quest_openxr")
        else None,
        abi=_android_string(android, "abi", "arm64-v8a"),
        platform=_android_string(android, "platform", "android-26"),
    )


def _validate_supported_target(target: str) -> None:
    if target not in SUPPORTED_TARGETS:
        raise UnsupportedBuildTargetError(target)


def _validate_target_option_blocks(profile: BuildProfile) -> None:
    allowed_blocks = TARGET_OPTION_BLOCKS[profile.target]
    supported_block_names = set(TARGET_OPTION_BLOCKS["desktop"])
    supported_block_names.update(TARGET_OPTION_BLOCKS["android"])
    supported_block_names.update(TARGET_OPTION_BLOCKS["quest_openxr"])

    for key, value in profile.data.items():
        if key in COMMON_PROFILE_KEYS or key in allowed_blocks:
            continue
        if key in supported_block_names or isinstance(value, dict):
            raise ProfileBuildError(
                f"profile '{profile.name}' target '{profile.target}' does not support option block '{key}'"
            )


def _target_options(profile: BuildProfile) -> dict[str, object]:
    options: dict[str, object] = {}
    allowed_blocks = TARGET_OPTION_BLOCKS[profile.target]
    for key in allowed_blocks:
        value = profile.data.get(key)
        if value is not None:
            if not isinstance(value, dict):
                raise ProfileBuildError(f"profile '{profile.name}' field '{key}' must be an object")
            options[key] = dict(value)
    return options


def _target_display_name(target: str) -> str:
    if target == "desktop":
        return "Desktop"
    if target == "android":
        return "Android"
    if target == "quest_openxr":
        return "Quest/OpenXR"
    return target


def _target_termin_root(
    profile: BuildProfile,
    android: Mapping[str, Any],
) -> Path | None:
    if profile.target not in ("android", "quest_openxr"):
        return None
    return _path_from_mapping(
        android,
        "termin_root",
        _profile_path(profile, "termin_root", None),
        profile.project_root,
    )


def _target_build_script(
    profile: BuildProfile,
    android: Mapping[str, Any],
    openxr: Mapping[str, Any],
) -> Path | None:
    if profile.target == "android":
        return _path_from_mapping(
            android,
            "build_script",
            _profile_path(profile, "build_script", None),
            profile.project_root,
        )
    if profile.target == "quest_openxr":
        return _path_from_mapping(
            openxr,
            "build_script",
            _profile_path(profile, "build_script", None),
            profile.project_root,
        )
    return None


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Execute a resolved Termin build profile")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build a resolved project profile")
    build_parser.add_argument("--project-root", type=Path, required=True)
    build_parser.add_argument("--profiles-path", type=Path, required=True)
    build_parser.add_argument("--profile", required=True)
    build_parser.add_argument("--target", default=None)
    build_parser.add_argument("--shader-compiler", type=Path, default=None)

    desktop_parser = subparsers.add_parser(
        "desktop",
        help="Build desktop project artifacts using the legacy direct argument form",
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
        help="Add a runtime shader artifact target. Repeat for multiple targets.",
    )
    desktop_parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="Write build.json and manifest.json without copying resource files",
    )

    return parser


def _build_legacy_desktop(args: argparse.Namespace) -> int:
    if args.manifest_only:
        print("warning: --manifest-only is ignored by the desktop runtime package backend")

    project_root = args.project_root.resolve()
    result = build_desktop_project(
        project_root=project_root,
        entry_scene=_resolve_project_path(project_root, args.entry_scene),
        output_dir=_resolve_project_path(project_root, args.output_dir),
        shader_compiler=args.shader_compiler,
        shader_targets=tuple(args.shader_targets) if args.shader_targets is not None else None,
    )
    _print_desktop_result(result)
    return _exit_code_for_diagnostics(result.diagnostics)


def _read_json_object(path: Path) -> Mapping[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except OSError as exc:
        raise ProfileBuildError(f"failed to read build profiles file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ProfileBuildError(f"failed to parse build profiles file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ProfileBuildError(f"build profiles root must be a JSON object: {path}")
    return data


def _validate_schema_version(data: Mapping[str, Any], context: str) -> None:
    value = data.get("version")
    if value is None:
        raise ProfileBuildError(
            f"{context} must contain integer field 'version' with value "
            f"{BUILD_PROFILE_SCHEMA_VERSION}"
        )
    if not isinstance(value, int):
        raise ProfileBuildError(f"{context} field 'version' must be an integer")
    if value != BUILD_PROFILE_SCHEMA_VERSION:
        raise ProfileBuildError(
            f"{context} has unsupported build profile schema version {value}; "
            f"supported version is {BUILD_PROFILE_SCHEMA_VERSION}"
        )


def _required_object(data: Mapping[str, Any], key: str, context: str) -> Mapping[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ProfileBuildError(f"{context} must contain object field '{key}'")
    return value


def _optional_object(data: Mapping[str, Any], key: str, context: str) -> Mapping[str, Any]:
    value = data.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ProfileBuildError(f"{context} field '{key}' must be an object")
    return value


def _required_string(data: Mapping[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or value == "":
        raise ProfileBuildError(f"{context} must contain non-empty string field '{key}'")
    return value


def _profile_string(profile: BuildProfile, key: str, default: str) -> str:
    value = profile.data.get(key)
    if value is None:
        return default
    if not isinstance(value, str) or value == "":
        raise ProfileBuildError(f"profile '{profile.name}' field '{key}' must be a non-empty string")
    return value


def _profile_string_choice(
    profile: BuildProfile,
    key: str,
    default: str,
    supported_values: Sequence[str],
) -> str:
    value = _profile_string(profile, key, default)
    if value not in supported_values:
        supported = ", ".join(supported_values)
        raise ProfileBuildError(
            f"profile '{profile.name}' field '{key}' has unsupported value '{value}'. "
            f"Supported values: {supported}"
        )
    return value


def _profile_shader_targets(profile: BuildProfile) -> tuple[str, ...] | None:
    value = profile.data.get("shader_targets")
    if value is None:
        return None
    if not isinstance(value, list):
        raise ProfileBuildError(f"profile '{profile.name}' field 'shader_targets' must be a list")

    normalized: list[str] = []
    seen: set[str] = set()
    for index, target in enumerate(value):
        if not isinstance(target, str) or target == "":
            raise ProfileBuildError(
                f"profile '{profile.name}' field 'shader_targets[{index}]' must be a non-empty string"
            )
        if target not in SUPPORTED_SHADER_TARGETS:
            supported = ", ".join(SUPPORTED_SHADER_TARGETS)
            raise ProfileBuildError(
                f"profile '{profile.name}' field 'shader_targets[{index}]' has unsupported "
                f"value '{target}'. Supported values: {supported}"
            )
        if target in seen:
            continue
        seen.add(target)
        normalized.append(target)

    if not normalized:
        raise ProfileBuildError(f"profile '{profile.name}' field 'shader_targets' must not be empty")
    return tuple(normalized)


def _validate_shader_target_tools(
    profile: BuildProfile,
    shader_targets: tuple[str, ...] | None,
    shader_compiler: Path | None,
    sdk_root: Path | None,
) -> None:
    if profile.target != "desktop":
        return
    if shader_targets is None or "d3d11" not in shader_targets:
        return
    if shader_compiler is not None:
        return
    if _d3d11_shader_compiler_available(sdk_root):
        return
    raise ProfileBuildError(
        f"profile '{profile.name}' requests shader target 'd3d11', but fxc was not found. "
        "D3D11 shader artifacts require TERMIN_FXC, fxc in PATH, or fxc under TERMIN_SDK/bin. "
        "For a Linux desktop build, use shader_targets [\"vulkan\", \"opengl\"] or build the "
        "D3D11 artifacts on a Windows SDK host."
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

    if os.name == "nt":
        return True
    return False


def _android_string(android: Mapping[str, Any], key: str, default: str) -> str:
    value = android.get(key)
    if value is None:
        return default
    if not isinstance(value, str) or value == "":
        raise ProfileBuildError(f"android field '{key}' must be a non-empty string")
    return value


def _path_from_mapping(
    data: Mapping[str, Any],
    key: str,
    default: Path | None,
    base_dir: Path | None = None,
) -> Path | None:
    value = data.get(key)
    if value is None:
        return default
    if not isinstance(value, str) or value == "":
        raise ProfileBuildError(f"field '{key}' must be a non-empty string")
    path = Path(value).expanduser()
    if base_dir is not None and not path.is_absolute():
        path = base_dir / path
    return path


def _profile_path(profile: BuildProfile, key: str, default: Path | None) -> Path | None:
    return _path_from_mapping(profile.data, key, default, profile.project_root)


def _desktop_path(profile: BuildProfile, key: str) -> Path | None:
    desktop = _optional_object(profile.data, "desktop", context=f"profile '{profile.name}'")
    return _path_from_mapping(desktop, key, None, profile.project_root)


def _android_path(profile: BuildProfile, android: Mapping[str, Any], key: str) -> Path | None:
    return _path_from_mapping(android, key, None, profile.project_root)


def _resolve_project_path(project_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    return candidate.resolve()


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
    with manifest_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ProfileBuildError(f"runtime package manifest must be a JSON object: {manifest_path}")
    resources = data.get("resources")
    if isinstance(resources, list):
        return resources
    return []


def _print_diagnostics(diagnostics: Sequence[Any]) -> None:
    for diagnostic in diagnostics:
        print(f"{diagnostic.level}: {diagnostic.path}: {diagnostic.message}")


def _exit_code_for_diagnostics(diagnostics: Sequence[Any]) -> int:
    if any(diagnostic.level == "error" for diagnostic in diagnostics):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
