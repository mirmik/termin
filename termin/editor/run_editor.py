import sys
import warnings

# Suppress SDL2 informational warning about using pysdl2-dll binaries (Windows)
warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll")

from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import QApplication

from termin.editor.editor_window import EditorWindow
from termin.visualization.core.scene import Scene
from termin.visualization.core.world import VisualizationWorld
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


def init_editor(debug_resource: str | None = None, no_scene: bool = False):
    """
    Initialize editor and setup callbacks.
    Called from C++ before EngineCore.run().
    Does NOT call engine.run() - that's done in C++.
    """
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
    world = VisualizationWorld()
    if no_scene:
        scene = None
    else:
        scene = build_scene(world)

    # Apply dark theme
    apply_dark_palette(app)

    # Create editor window with scene_manager from EngineCore
    win = EditorWindow(world, scene, sdl_backend, engine.scene_manager)
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
    import argparse
    parser = argparse.ArgumentParser(description="Run termin editor")
    parser.add_argument(
        "--debug-resource",
        type=str,
        default=None,
        help="Open framegraph debugger with this resource (e.g., shadow_maps, color)"
    )
    parser.add_argument(
        "--no-scene",
        action="store_true",
        help="Start editor without opening a scene"
    )
    args = parser.parse_args()
    run_editor(debug_resource=args.debug_resource, no_scene=args.no_scene)
