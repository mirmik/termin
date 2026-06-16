"""
Command-line entry point for Termin Player.

Usage:
    python -m termin.player path/to/project --scene main.scene
    python -m termin.player --build dist/MyGame/build.json
    python -m termin.player --bundle dist/MyGame/app.json
"""

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Run a Termin project in standalone player mode"
    )
    parser.add_argument(
        "project",
        type=str,
        nargs="?",
        help="Path to project directory",
    )
    parser.add_argument(
        "--build", "-b",
        type=str,
        default=None,
        help="Path to build.json produced by termin.project_builder",
    )
    parser.add_argument(
        "--bundle",
        "--app",
        type=str,
        default=None,
        help="Path to app.json produced by termin build",
    )
    parser.add_argument(
        "--scene", "-s",
        type=str,
        default=None,
        help="Scene file to load (default: first .scene file found)",
    )
    parser.add_argument(
        "--width", "-W",
        type=int,
        default=1280,
        help="Window width (default: 1280)",
    )
    parser.add_argument(
        "--height", "-H",
        type=int,
        default=720,
        help="Window height (default: 720)",
    )
    parser.add_argument(
        "--title", "-t",
        type=str,
        default="Termin Player",
        help="Window title",
    )

    args = parser.parse_args()

    if args.build is not None and args.bundle is not None:
        parser.error("--build and --bundle are mutually exclusive")

    if args.bundle is not None:
        app_json_path = Path(args.bundle)
        if not app_json_path.exists():
            print(f"Error: Bundle app manifest does not exist: {app_json_path}")
            sys.exit(1)

        from termin.player import run_bundle

        run_bundle(
            app_manifest_path=app_json_path,
            width=args.width,
            height=args.height,
            title=args.title,
        )
        return

    if args.build is not None:
        build_json_path = Path(args.build)
        if not build_json_path.exists():
            print(f"Error: Build file does not exist: {build_json_path}")
            sys.exit(1)

        try:
            with open(build_json_path, "r", encoding="utf-8") as f:
                build_data = json.load(f)
        except Exception as e:
            print(f"Error: Failed to read build file {build_json_path}: {e}")
            sys.exit(1)

        entry_scene = build_data.get("entry_scene")
        asset_manifest = build_data.get("asset_manifest")
        if not isinstance(entry_scene, str) or entry_scene == "":
            print(f"Error: build.json has no entry_scene: {build_json_path}")
            sys.exit(1)
        if not isinstance(asset_manifest, str) or asset_manifest == "":
            print(f"Error: build.json has no asset_manifest: {build_json_path}")
            sys.exit(1)

        from termin.player import run_build

        run_build(
            build_json_path=build_json_path,
            width=args.width,
            height=args.height,
            title=args.title,
        )
        return

    if args.project is None:
        parser.error("project is required unless --build or --bundle is used")

    project_path = Path(args.project)
    if not project_path.exists():
        print(f"Error: Project path does not exist: {project_path}")
        sys.exit(1)

    # Find scene file
    scene_name = args.scene
    if scene_name is None:
        # Look for first .scene file (recursively)
        scene_files = list(project_path.rglob("*.scene"))
        if not scene_files:
            print(f"Error: No .scene files found in {project_path}")
            sys.exit(1)
        # Use relative path from project root
        scene_name = str(scene_files[0].relative_to(project_path))
        print(f"Using scene: {scene_name}")

    from termin.player import run_project

    run_project(
        project_path=project_path,
        scene_name=scene_name,
        width=args.width,
        height=args.height,
        title=args.title,
    )


if __name__ == "__main__":
    main()
