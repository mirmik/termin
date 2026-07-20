"""Canonical editor entry point with native UI as the production default."""

from __future__ import annotations

import sys


def _parse_editor_args() -> tuple[str | None, str | None, str]:
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
        print("  --ui=BACKEND        Select native (default) or legacy tcgui for comparison")
        print("  -h, --help           Show this help message and exit")
        return "__help__", None, "native"

    debug_resource = None
    ui_backend = "native"
    positional: list[str] = []
    i = 0
    while i < len(args):
        if args[i] == "--debug-resource" and i + 1 < len(args):
            debug_resource = args[i + 1]
            i += 2
        elif args[i].startswith("--ui="):
            ui_backend = args[i].split("=", 1)[1]
            if ui_backend not in ("tcgui", "native"):
                print(f"Error: unsupported UI backend '{ui_backend}'.", flush=True)
                return "__error__", None, ui_backend
            if ui_backend == "tcgui":
                print(
                    "[WARN] Starting legacy tcgui frontend for migration comparison; "
                    "termin-gui-native remains the production default.",
                    flush=True,
                )
            i += 1
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
            return "__error__", None, ui_backend

    return project, debug_resource, ui_backend


def init_editor(engine, debug_resource: str | None = None, no_scene: bool = False):
    """Initialize the selected editor frontend and return its session."""
    cli_project, cli_debug, ui_backend = _parse_editor_args()
    if cli_project in ("__help__", "__error__"):
        sys.exit(0 if cli_project == "__help__" else 1)
    if cli_debug is not None:
        debug_resource = cli_debug
    if cli_project is not None:
        from termin.launcher.recent import write_launch_project

        write_launch_project(cli_project)

    if ui_backend == "tcgui":
        from termin.editor_tcgui.run_editor import init_editor_tcgui

        return init_editor_tcgui(
            engine,
            debug_resource=debug_resource,
            no_scene=no_scene,
        )

    from termin.editor_native.run_editor import init_editor_native

    return init_editor_native(
        engine,
        debug_resource=debug_resource,
        no_scene=no_scene,
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
