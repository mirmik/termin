"""Profile build backend used by the C++ termin_builder entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from termin.project_builder import build_project


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
    result = build_project(
        project_root=args.project_root,
        entry_scene=args.entry_scene,
        output_dir=args.output_dir,
        copy_files=not args.manifest_only,
        compile_asset_shaders=True,
        include_engine_shaders=True,
        shader_compiler=args.shader_compiler,
    )

    print(f"Build: {result.build_json_path}")
    print(f"Manifest: {result.manifest_json_path}")
    print(f"Resources: {len(result.manifest.resources)}")
    for diagnostic in result.manifest.diagnostics:
        print(f"{diagnostic.level}: {diagnostic.path}: {diagnostic.message}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
