import sys
import warnings

# Suppress SDL2 informational warning about using pysdl2-dll binaries (Windows)
warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll")

from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import QApplication

from termin.editor.editor_window import EditorWindow
from termin.visualization.core.scene import Scene
from termin.visualization.core.world import World
from termin.visualization.platform.backends import (
    OpenGLGraphicsBackend,
    set_default_graphics_backend,
)
from termin.visualization.platform.backends.sdl_embedded import SDLEmbeddedWindowBackend


def build_scene(world):
    scene = Scene.create(name="default")
    world.add_scene(scene)
    return scene


def apply_dark_palette(app: QApplication):
    app.setStyle("Fusion")

    palette = QPalette()

    bg = QColor(30, 30, 30)
    window = QColor(37, 37, 38)
    base = QColor(45, 45, 48)
    text = QColor(220, 220, 220)
    disabled_text = QColor(128, 128, 128)
    highlight = QColor(0, 120, 215)

    palette.setColor(QPalette.ColorRole.Window, window)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, base)
    palette.setColor(QPalette.ColorRole.AlternateBase, bg)
    palette.setColor(QPalette.ColorRole.ToolTipBase, base)
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, window)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))

    palette.setColor(QPalette.ColorRole.Highlight, highlight)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))

    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled_text)

    app.setPalette(palette)


def _parse_editor_args():
    """Parse command-line arguments for the editor.

    Returns (project, debug_resource, ui_backend) or exits.
    ui_backend is one of: 'qt' (default), 'tcgui'
    """
    args = sys.argv[1:]

    if '-h' in args or '--help' in args:
        print("Usage: termin_editor [OPTIONS] [PROJECT]")
        print()
        print("Termin scene editor.")
        print()
        print("Arguments:")
        print("  PROJECT              Path to .terminproj file or project directory")
        print()
        print("Options:")
        print("  --ui=qt|tcgui        UI backend (default: qt)")
        print("  --debug-resource RES Open framegraph debugger with this resource")
        print("  -h, --help           Show this help message and exit")
        return "__help__", None, "qt"

    debug_resource = None
    ui_backend = "qt"
    positional = []
    i = 0
    while i < len(args):
        if args[i] == '--debug-resource' and i + 1 < len(args):
            debug_resource = args[i + 1]
            i += 2
        elif args[i].startswith('--ui='):
            ui_backend = args[i].split('=', 1)[1]
            i += 1
        elif not args[i].startswith('-'):
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


def init_editor(debug_resource: str | None = None, no_scene: bool = False):
    """
    Initialize editor and setup callbacks.
    Called from C++ before EngineCore.run().
    Does NOT call engine.run() - that's done in C++.
    """
    # Parse CLI args (project path, --debug-resource, --ui)
    cli_project, cli_debug, ui_backend = _parse_editor_args()
    if cli_project in ("__help__", "__error__"):
        sys.exit(0 if cli_project == "__help__" else 1)
    if cli_debug is not None:
        debug_resource = cli_debug
    if cli_project is not None:
        from termin.launcher.recent import write_launch_project
        write_launch_project(cli_project)

    # Delegate to tcgui editor if requested
    if ui_backend == "tcgui":
        from termin.editor_tcgui.run_editor import init_editor_tcgui
        init_editor_tcgui(debug_resource=debug_resource, no_scene=no_scene)
        return

    from termin._native import EngineCore

    # Get EngineCore instance (created in C++)
    engine = EngineCore.instance()
    if engine is None:
        raise RuntimeError("EngineCore not created. Must be called from C++ entry point.")

    # Create Qt application
    app = QApplication(sys.argv)

    # Initialize SDL
    import sdl2
    if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
        raise RuntimeError(f"Failed to initialize SDL: {sdl2.SDL_GetError()}")

    # Setup graphics backend
    graphics = OpenGLGraphicsBackend.get_instance()
    set_default_graphics_backend(graphics)

    # Create SDL embedded backend
    sdl_backend = SDLEmbeddedWindowBackend(graphics=graphics)

    # Create world and scene
    world = World()
    if no_scene:
        scene = None
    else:
        scene = build_scene(world)

    # Apply dark theme
    apply_dark_palette(app)

    # Create editor window with scene_manager from EngineCore
    win = EditorWindow(world, scene, sdl_backend, engine.scene_manager, graphics=graphics)
    win.showMaximized()

    # Process events to ensure window is visible
    app.processEvents()

    # Open debugger if requested
    if debug_resource:
        win.open_framegraph_debugger(initial_resource=debug_resource)
        app.processEvents()

    # Render first frame
    sdl_backend.poll_events()
    engine.scene_manager.request_render()
    engine.scene_manager.tick_and_render(0.016)

    # Setup callbacks for main loop
    def poll_events():
        app.processEvents()
        sdl_backend.poll_events()

    def should_continue():
        return not win.should_close()

    def on_shutdown():
        sdl_backend.terminate()
        sdl2.SDL_Quit()

    engine.set_poll_events_callback(poll_events)
    engine.set_should_continue_callback(should_continue)
    engine.set_on_shutdown_callback(on_shutdown)


def run_editor(debug_resource: str | None = None, no_scene: bool = False):
    """
    Run the editor (legacy entry point).
    Must be called from C++ entry point.
    """
    from termin._native import EngineCore

    engine = EngineCore.instance()
    if engine is None:
        raise RuntimeError(
            "run_editor() must be called from C++ entry point (termin_editor). "
            "EngineCore is created in C++."
        )

    init_editor(debug_resource=debug_resource, no_scene=no_scene)
    engine.run()


if __name__ == "__main__":
    # Args parsed inside init_editor/_parse_editor_args
    run_editor()
