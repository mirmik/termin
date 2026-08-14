from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


class ArtifactResolutionError(RuntimeError):
    pass


SDK_CAPABILITIES_NAME = "termin-sdk-capabilities.json"


def _cmake_cache_value(cache_path: Path, name: str) -> str | None:
    if not cache_path.is_file():
        raise ArtifactResolutionError(f"CMake cache is missing for the current C++ test graph: {cache_path}")

    prefix = f"{name}:"
    for line in cache_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith(prefix):
            continue
        _, separator, value = line.partition("=")
        if separator:
            return value
    return None


def resolve_shader_compiler(
    build_dir: Path,
    configuration: str,
    platform: str,
) -> Path:
    if not configuration or "/" in configuration or "\\" in configuration or configuration in {".", ".."}:
        raise ArtifactResolutionError(f"invalid CMake test configuration: {configuration!r}")

    resolved_build_dir = build_dir.resolve()
    configuration_types = _cmake_cache_value(
        resolved_build_dir / "CMakeCache.txt",
        "CMAKE_CONFIGURATION_TYPES",
    )
    multi_config = bool(configuration_types)

    normalized_platform = platform.lower()
    if normalized_platform in {"windows", "win32"}:
        executable_name = "termin_shaderc.exe"
    elif normalized_platform in {"linux", "darwin"}:
        executable_name = "termin_shaderc"
    else:
        raise ArtifactResolutionError(f"unsupported test artifact platform: {platform!r}")

    compiler_dir = resolved_build_dir / "bin"
    if multi_config:
        compiler_dir /= configuration
    compiler_path = compiler_dir / executable_name
    if not compiler_path.is_file():
        graph_kind = "multi-config" if multi_config else "single-config"
        raise ArtifactResolutionError(
            "termin_shaderc produced by the current C++ test graph is missing: "
            f"{compiler_path} ({graph_kind}, configuration {configuration}). "
            "Run the C++ test build successfully before Python tests."
        )
    return compiler_path


def resolve_sdk_shader_compiler(sdk_root: Path, platform: str) -> Path:
    resolved_sdk_root = sdk_root.resolve()
    manifest_path = resolved_sdk_root / SDK_CAPABILITIES_NAME
    if not manifest_path.is_file():
        raise ArtifactResolutionError(f"SDK capability manifest is missing: {manifest_path}. Run 'task build' first.")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ArtifactResolutionError(f"failed to read SDK capability manifest {manifest_path}: {error}") from error

    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        raise ArtifactResolutionError(f"unsupported SDK capability manifest in {manifest_path}")
    tools = manifest.get("tools")
    if not isinstance(tools, dict):
        raise ArtifactResolutionError(f"SDK capability manifest has no tools object: {manifest_path}")
    relative_path = tools.get("termin_shaderc")
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise ArtifactResolutionError(
            f"SDK does not declare the termin_shaderc tool: {manifest_path}. Run 'task build' first."
        )

    normalized_platform = platform.lower()
    if normalized_platform in {"windows", "win32"}:
        executable_name = "termin_shaderc.exe"
    elif normalized_platform in {"linux", "darwin"}:
        executable_name = "termin_shaderc"
    else:
        raise ArtifactResolutionError(f"unsupported SDK artifact platform: {platform!r}")

    declared_path = Path(relative_path)
    if declared_path.is_absolute():
        raise ArtifactResolutionError(f"SDK termin_shaderc path must be relative: {relative_path!r}")
    compiler_path = (resolved_sdk_root / declared_path).resolve()
    try:
        compiler_path.relative_to(resolved_sdk_root)
    except ValueError as error:
        raise ArtifactResolutionError(f"SDK termin_shaderc path escapes the SDK root: {relative_path!r}") from error
    if compiler_path.name != executable_name:
        raise ArtifactResolutionError(
            f"SDK termin_shaderc declaration has the wrong executable name: {relative_path!r} for platform {platform}"
        )
    if not compiler_path.is_file():
        raise ArtifactResolutionError(
            f"SDK-declared termin_shaderc is missing: {compiler_path}. Run 'task build' first."
        )
    return compiler_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve artifacts from CMake build graphs and installed SDKs.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    shader_parser = subparsers.add_parser("shader-compiler")
    shader_parser.add_argument("--build-dir", type=Path, required=True)
    shader_parser.add_argument("--configuration", required=True)
    shader_parser.add_argument(
        "--platform",
        choices=("linux", "windows"),
        required=True,
    )
    sdk_shader_parser = subparsers.add_parser("sdk-shader-compiler")
    sdk_shader_parser.add_argument("--sdk-root", type=Path, required=True)
    sdk_shader_parser.add_argument(
        "--platform",
        choices=("linux", "windows"),
        required=True,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "shader-compiler":
            print(
                resolve_shader_compiler(
                    args.build_dir,
                    args.configuration,
                    args.platform,
                )
            )
            return 0
        if args.command == "sdk-shader-compiler":
            print(resolve_sdk_shader_compiler(args.sdk_root, args.platform))
            return 0
    except ArtifactResolutionError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
