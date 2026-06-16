"""Profile build backend used by the C++ termin_builder entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from termin.project_build import build_desktop_project


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute a resolved Termin build profile")
    subparsers = parser.add_subparsers(dest="command", required=True)

    desktop_parser = subparsers.add_parser("desktop", help="Build desktop project artifacts")
    desktop_parser.add_argument("--project-root", type=Path, required=True)
    desktop_parser.add_argument("--entry-scene", type=Path, required=True)
    desktop_parser.add_argument("--output-dir", type=Path, required=True)
    desktop_parser.add_argument("--shader-compiler", type=Path, default=None)
    desktop_parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="Write build.json and manifest.json without copying resource files",
    )

    args = parser.parse_args()

    if args.command == "desktop":
        return _build_desktop(args)

    return 1


def _build_desktop(args: argparse.Namespace) -> int:
    if args.manifest_only:
        print("warning: --manifest-only is ignored by the desktop runtime package backend")

    result = build_desktop_project(
        project_root=args.project_root,
        entry_scene=args.entry_scene,
        output_dir=args.output_dir,
        shader_compiler=args.shader_compiler,
    )

    print(f"Bundle: {result.dist_dir}")
    print(f"App manifest: {result.app_manifest_path}")
    print(f"Package: {result.package_result.package_dir}")
    print(f"Manifest: {result.package_result.manifest_path}")
    print(f"Resources: {len(_manifest_resources(result.package_result.manifest_path))}")
    for diagnostic in result.diagnostics:
        print(f"{diagnostic.level}: {diagnostic.path}: {diagnostic.message}")
    return 0


def _manifest_resources(manifest_path: Path) -> list[object]:
    import json

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    resources = data.get("resources")
    if isinstance(resources, list):
        return resources
    return []


if __name__ == "__main__":
    sys.exit(main())
