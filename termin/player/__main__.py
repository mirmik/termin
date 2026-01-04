"""
Command-line entry point for Termin Player.

Usage:
    python -m termin.player path/to/project --scene main.scene
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Run a Termin project in standalone player mode"
    )
    parser.add_argument(
        "project",
        type=str,
        help="Path to project directory",
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

    project_path = Path(args.project)
    if not project_path.exists():
        print(f"Error: Project path does not exist: {project_path}")
        sys.exit(1)

    # Find scene file
    scene_name = args.scene
    if scene_name is None:
        # Look for first .scene file
        scene_files = list(project_path.glob("*.scene"))
        if not scene_files:
            print(f"Error: No .scene files found in {project_path}")
            sys.exit(1)
        scene_name = scene_files[0].name
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
