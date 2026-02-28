"""Entry point for the tcgui-based editor."""

from __future__ import annotations

import sys

from tcbase import log


def init_editor_tcgui(debug_resource: str | None = None, no_scene: bool = False) -> None:
    """Initialize the tcgui editor and setup engine callbacks.

    Called from C++ before EngineCore.run(). Does NOT call engine.run().
    """
    from termin._native import EngineCore

    engine = EngineCore.instance()
    if engine is None:
        raise RuntimeError("EngineCore not created. Must be called from C++ entry point.")

    # Setup graphics backend (OpenGL)
    from termin.visualization.platform.backends import (
        OpenGLGraphicsBackend,
        set_default_graphics_backend,
    )
    graphics = OpenGLGraphicsBackend.get_instance()
    set_default_graphics_backend(graphics)

    # Create world and scene
    from termin.visualization.core.world import World
    from termin.visualization.core.scene import Scene

    world = World()
    if no_scene:
        initial_scene = None
    else:
        initial_scene = Scene.create(name="default")
        world.add_scene(initial_scene)

    # Create tcgui UI
    from tcgui.widgets.ui import UI
    ui = UI(graphics=graphics)

    # Create editor window
    from termin.editor_tcgui.editor_window import EditorWindowTcgui
    win = EditorWindowTcgui(
        world=world,
        initial_scene=initial_scene,
        scene_manager=engine.scene_manager,
        graphics=graphics,
    )
    win.build(ui)

    # First render
    engine.scene_manager.request_render()
    engine.scene_manager.tick_and_render(0.016)

    # Setup engine callbacks
    def poll_events() -> None:
        ui.poll()

    def should_continue() -> bool:
        return not win.should_close()

    def on_shutdown() -> None:
        pass

    engine.set_poll_events_callback(poll_events)
    engine.set_should_continue_callback(should_continue)
    engine.set_on_shutdown_callback(on_shutdown)


def run_editor_tcgui(debug_resource: str | None = None, no_scene: bool = False) -> None:
    """Run the tcgui editor (legacy entry point for C++ callers)."""
    from termin._native import EngineCore

    engine = EngineCore.instance()
    if engine is None:
        raise RuntimeError(
            "run_editor_tcgui() must be called from C++ entry point. "
            "EngineCore is created in C++."
        )

    init_editor_tcgui(debug_resource=debug_resource, no_scene=no_scene)
    engine.run()
