"""
Command-line entry point for Termin Player.

Usage:
    python -m termin.player path/to/project --scene main.scene
    python -m termin.player path/to/project --scene main.scene --headless
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
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run project scene update loop without window, RenderingManager, or rendering",
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=None,
        help="Number of frames to run in --headless mode (default: run until quit/interrupted)",
    )
    parser.add_argument(
        "--dt",
        type=float,
        default=1.0 / 60.0,
        help="Simulation dt per frame in --headless mode (default: 1/60)",
    )
    parser.add_argument(
        "--no-assets",
        action="store_true",
        help="Skip source asset scanning in --headless mode",
    )
    parser.add_argument(
        "--no-modules",
        action="store_true",
        help="Skip project module loading in --headless mode",
    )
    parser.add_argument(
        "--mcp",
        action="store_true",
        help="Enable the player MCP diagnostics endpoint",
    )
    parser.add_argument(
        "--mcp-host",
        type=str,
        default=None,
        help="Player MCP bind host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--mcp-port",
        type=int,
        default=None,
        help="Player MCP bind port (default: 8766)",
    )
    parser.add_argument(
        "--mcp-token",
        type=str,
        default=None,
        help="Player MCP bearer token (default: generated)",
    )
    parser.add_argument(
        "--mcp-session-file",
        type=str,
        default=None,
        help="Player MCP session file path (default: /tmp/termin-player-mcp.json)",
    )

    args = parser.parse_args()
    mcp_options = _mcp_options_from_args(args)

    if args.build is not None and args.bundle is not None:
        parser.error("--build and --bundle are mutually exclusive")
    if args.headless and (args.build is not None or args.bundle is not None):
        parser.error("--headless runs source projects only; --build and --bundle are render runtimes")
    if args.frames is not None and args.frames < 0:
        parser.error("--frames must be non-negative")
    if args.dt < 0.0:
        parser.error("--dt must be non-negative")

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
            mcp_enabled=args.mcp,
            mcp_options=mcp_options,
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
            mcp_enabled=args.mcp,
            mcp_options=mcp_options,
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

    if args.headless:
        from termin.player import run_headless_project

        stats = run_headless_project(
            project_path=project_path,
            scene_name=scene_name,
            frames=args.frames,
            dt=args.dt,
            load_assets=not args.no_assets,
            load_modules=not args.no_modules,
        )
        if stats.exit_code != 0:
            sys.exit(stats.exit_code)
        return

    from termin.player import run_project

    run_project(
        project_path=project_path,
        scene_name=scene_name,
        width=args.width,
        height=args.height,
        title=args.title,
        mcp_enabled=args.mcp,
        mcp_options=mcp_options,
    )


def _mcp_options_from_args(args) -> dict[str, object]:
    options: dict[str, object] = {}
    if args.mcp_host is not None:
        options["host"] = args.mcp_host
    if args.mcp_port is not None:
        options["port"] = args.mcp_port
    if args.mcp_token is not None:
        options["token"] = args.mcp_token
    if args.mcp_session_file is not None:
        options["session_file"] = args.mcp_session_file
    return options


if __name__ == "__main__":
    main()
