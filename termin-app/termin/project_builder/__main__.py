"""Command-line entry point for legacy dev project export."""

from __future__ import annotations

import argparse
from pathlib import Path

from termin.project_builder import export_legacy_project


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export legacy Termin dev/play-mode build.json/assets artifacts. "
            "Packaged builds use termin.project_build.profile_build."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser(
        "legacy-dev-export",
        help="Export legacy broad-copy dev/play-mode artifacts",
    )
    build_parser.add_argument("project", type=Path, help="Path to project root")
    build_parser.add_argument("--scene", "-s", type=Path, required=True, help="Entry .scene path")
    build_parser.add_argument("--out", "-o", type=Path, required=True, help="Output directory")
    build_parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="Write build.json and manifest.json without copying resource files",
    )

    args = parser.parse_args(argv)

    if args.command == "legacy-dev-export":
        result = export_legacy_project(
            project_root=args.project,
            entry_scene=args.scene,
            output_dir=args.out,
            copy_files=not args.manifest_only,
        )
        print(f"Legacy dev export: {result.build_json_path}")
        print(f"Manifest: {result.manifest_json_path}")
        print(f"Resources: {len(result.manifest.resources)}")
        for diagnostic in result.manifest.diagnostics:
            print(f"{diagnostic.level}: {diagnostic.path}: {diagnostic.message}")
        return 0

    return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
