"""Canonical editor entry point with native UI as the production default."""

from __future__ import annotations

from dataclasses import dataclass
import sys


@dataclass(frozen=True, slots=True)
class EditorLaunchOptions:
    project: str | None = None
    debug_resource: str | None = None
    composition: str = "windowed"
    width: int = 1280
    height: int = 720
    backend: str = "vulkan"
    frames: int = 0
    exit_code: int | None = None


def _parse_extent(value: str) -> tuple[int, int]:
    try:
        width_text, height_text = value.lower().split("x", 1)
        width = int(width_text)
        height = int(height_text)
    except (TypeError, ValueError) as error:
        raise ValueError("offscreen extent must have the form WIDTHxHEIGHT") from error
    if width <= 0 or height <= 0:
        raise ValueError("offscreen extent dimensions must be positive")
    return width, height


def _parse_editor_args() -> EditorLaunchOptions:
    """Parse command-line arguments for the editor."""
    args = sys.argv[1:]

    if "-h" in args or "--help" in args:
        print("Usage: termin_editor [OPTIONS] [PROJECT]")
        print()
        print("Termin scene editor.")
        print()
        print("Arguments:")
        print("  PROJECT              Path to .terminproj file or project directory")
        print()
        print("Options:")
        print("  --debug-resource RES Open framegraph debugger with this resource")
        print("  --headless           Use isolated offscreen editor composition")
        print("  --offscreen-size WxH Fixed offscreen framebuffer extent")
        print("  --offscreen-backend NAME  Offscreen backend (vulkan or d3d11)")
        print("  --frames N           Stop after N editor frames (headless default: 1)")
        print("  -h, --help           Show this help message and exit")
        return EditorLaunchOptions(exit_code=0)

    debug_resource = None
    composition = "windowed"
    width = 1280
    height = 720
    backend = "vulkan"
    frames: int | None = None
    positional: list[str] = []
    i = 0
    while i < len(args):
        if args[i] == "--debug-resource" and i + 1 < len(args):
            debug_resource = args[i + 1]
            i += 2
        elif args[i] == "--headless":
            composition = "offscreen"
            i += 1
        elif args[i] == "--offscreen-size" and i + 1 < len(args):
            try:
                width, height = _parse_extent(args[i + 1])
            except ValueError as error:
                print(f"Error: {error}", flush=True)
                return EditorLaunchOptions(exit_code=1)
            composition = "offscreen"
            i += 2
        elif args[i] == "--offscreen-backend" and i + 1 < len(args):
            backend = args[i + 1].lower()
            if backend not in {"vulkan", "d3d11"}:
                print("Error: offscreen backend must be vulkan or d3d11", flush=True)
                return EditorLaunchOptions(exit_code=1)
            composition = "offscreen"
            i += 2
        elif args[i] == "--frames" and i + 1 < len(args):
            try:
                frames = int(args[i + 1])
            except ValueError:
                print("Error: --frames requires a positive integer", flush=True)
                return EditorLaunchOptions(exit_code=1)
            if frames <= 0:
                print("Error: --frames requires a positive integer", flush=True)
                return EditorLaunchOptions(exit_code=1)
            i += 2
        elif args[i].startswith("--ui"):
            print(
                "Error: the --ui option was removed; "
                "the native editor is the only supported frontend.",
                flush=True,
            )
            return EditorLaunchOptions(exit_code=1)
        elif not args[i].startswith("-"):
            positional.append(args[i])
            i += 1
        else:
            i += 1

    project = None
    if positional:
        from termin.launcher.recent import resolve_project_path

        project = resolve_project_path(positional[0])
        if project is None:
            print(f"Error: cannot find .terminproj at '{positional[0]}'", flush=True)
            return EditorLaunchOptions(exit_code=1)

    return EditorLaunchOptions(
        project=project,
        debug_resource=debug_resource,
        composition=composition,
        width=width,
        height=height,
        backend=backend,
        frames=(1 if composition == "offscreen" else 0) if frames is None else frames,
    )


def init_editor(engine, debug_resource: str | None = None, no_scene: bool = False):
    """Initialize the native editor frontend and return its session."""
    options = _parse_editor_args()
    if options.exit_code is not None:
        sys.exit(options.exit_code)
    if options.debug_resource is not None:
        debug_resource = options.debug_resource
    if options.project is not None:
        from termin.launcher.recent import write_launch_project

        write_launch_project(options.project)

    from termin.editor_native.editor_composition import EditorCompositionConfig
    from termin.editor_native.run_editor import init_editor_native

    return init_editor_native(
        engine,
        debug_resource=debug_resource,
        no_scene=no_scene,
        composition_config=EditorCompositionConfig(
            mode=options.composition,
            width=options.width,
            height=options.height,
            backend=options.backend,
            frame_limit=options.frames,
        ),
    )


def init_editor_from_host(engine_capsule):
    """Initialize from the C++ host's explicit borrowed-engine capsule."""
    from termin.engine import _borrow_engine_core

    return init_editor(_borrow_engine_core(engine_capsule))


def run_editor(engine, debug_resource: str | None = None, no_scene: bool = False) -> None:
    """Initialize and run an explicitly supplied engine."""
    session = init_editor(engine, debug_resource=debug_resource, no_scene=no_scene)
    try:
        engine.run()
    finally:
        try:
            session.prepare_engine_shutdown()
        finally:
            try:
                if not engine.shutdown():
                    raise RuntimeError("EngineCore refused editor shutdown")
            finally:
                session.close()


if __name__ == "__main__":
    raise RuntimeError("Use the termin_editor native host to run the editor")
