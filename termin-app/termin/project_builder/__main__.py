"""Command-line entry point for project build generation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from termin.project_builder import build_project


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a Termin project manifest")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build project artifacts")
    build_parser.add_argument("project", type=Path, help="Path to project root")
    build_parser.add_argument("--scene", "-s", type=Path, required=True, help="Entry .scene path")
    build_parser.add_argument("--out", "-o", type=Path, required=True, help="Output directory")
    build_parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="Write build.json and manifest.json without copying resource files",
    )

    args = parser.parse_args()

    if args.command == "build":
        result = build_project(
            project_root=args.project,
            entry_scene=args.scene,
            output_dir=args.out,
            copy_files=not args.manifest_only,
        )
        print(f"Build: {result.build_json_path}")
        print(f"Manifest: {result.manifest_json_path}")
        print(f"Resources: {len(result.manifest.resources)}")
        for diagnostic in result.manifest.diagnostics:
            print(f"{diagnostic.level}: {diagnostic.path}: {diagnostic.message}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
