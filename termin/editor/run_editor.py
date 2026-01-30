import sys
import time
import warnings

# Suppress SDL2 informational warning about using pysdl2-dll binaries (Windows)
warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll")

import numpy as np
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import QApplication
from PyQt6 import QtCore

from termin.editor.editor_window import EditorWindow
from termin.geombase import Pose3
from termin.geombase import GeneralPose3
from termin.mesh.mesh import CubeMesh, CylinderMesh, Mesh3
from termin.visualization.core.camera import PerspectiveCameraComponent, OrbitCameraController
from termin.visualization.core.entity import Entity
from termin.visualization.core.material import Material
from termin.visualization.core.scene import Scene
from termin.visualization.core.world import VisualizationWorld
from termin.visualization.platform.backends import (
    OpenGLGraphicsBackend,
    set_default_graphics_backend,
)
from termin.visualization.platform.backends.sdl_embedded import SDLEmbeddedWindowBackend
from termin.visualization.render.components import MeshRenderer
from termin.visualization.render.components.light_component import LightComponent
from termin.lighting import LightType, LightShadowParams


def build_scene(world):
    from termin.voxels.voxel_mesh import create_voxel_mesh

    scene = Scene(name="default")
    world.add_scene(scene)

    return scene


def apply_dark_palette(app: QApplication):
    app.setStyle("Fusion")  # более аккуратный стиль, чем дефолтный

    palette = QPalette()

    # Базовые цвета
    bg      = QColor(30, 30, 30)
    window  = QColor(37, 37, 38)
    base    = QColor(45, 45, 48)
    text    = QColor(220, 220, 220)
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

    # Отключённые элементы
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled_text)

    app.setPalette(palette)


def run_editor(debug_resource: str | None = None, no_scene: bool = False):
    """
    Run the editor.

    Args:
        debug_resource: If set, open framegraph debugger with this resource
                       (e.g., "shadow_maps", "color") from the first frame.
        no_scene: If True, start editor without any scene (no-scene mode).
    """
    # Create Qt application
    app = QApplication(sys.argv)

    # Initialize SDL once at startup
    import sdl2
    if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
        raise RuntimeError(f"Failed to initialize SDL: {sdl2.SDL_GetError()}")

    # Setup graphics backend
    graphics = OpenGLGraphicsBackend()
    set_default_graphics_backend(graphics)

    # Create SDL embedded backend for viewport rendering
    sdl_backend = SDLEmbeddedWindowBackend(graphics=graphics)

    # Create world and scene
    world = VisualizationWorld()
    if no_scene:
        scene = None
    else:
        scene = build_scene(world)

    # Apply dark theme
    apply_dark_palette(app)

    # Create editor window with SDL backend
    win = EditorWindow(world, scene, sdl_backend)
    win.showMaximized()

    # Process events to ensure window is visible
    app.processEvents()

    # Open debugger with specific resource if requested
    if debug_resource:
        win.open_framegraph_debugger(initial_resource=debug_resource)
        app.processEvents()  # Process debugger show event

    # Render first frame immediately to avoid showing uninitialized buffer
    sdl_backend.poll_events()
    win.scene_manager.request_render()
    win.scene_manager.tick(0.016)  # Render first frame

    # Main render loop
    target_fps = 60
    target_frame_time = 1.0 / target_fps
    last_time = time.perf_counter()

    while not win.should_close():
        current_time = time.perf_counter()
        dt = current_time - last_time
        last_time = current_time

        # Process Qt events (UI, menus, dialogs, etc.)
        app.processEvents()

        # Process SDL events (viewport input)
        sdl_backend.poll_events()

        # Tick editor (game mode update + render if needed)
        win.scene_manager.tick(dt)

        # Frame limiting - sleep if we're ahead of schedule
        elapsed = time.perf_counter() - current_time
        if elapsed < target_frame_time:
            time.sleep(target_frame_time - elapsed)

    # Cleanup
    sdl_backend.terminate()
    sdl2.SDL_Quit()


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
