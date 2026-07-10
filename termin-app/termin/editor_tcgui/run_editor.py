"""Entry point for the tcgui-based editor.

Runs on ``termin.display.BackendWindow`` — backend selection lives in
the env-var ``TERMIN_BACKEND`` (``opengl`` / ``vulkan``). No raw SDL+GL
window creation, no per-window tc_gpu_context, no SDL_GL_SHARE_WITH_
CURRENT_CONTEXT: the process owns a single tgfx2 IRenderDevice (borrowed
from the BackendWindow) and every renderer — UIRenderer, FBOSurface,
RenderEngine — lives on it.
"""

from __future__ import annotations

from pathlib import Path

from tcbase import Key, MouseButton, log
from tcgui.widgets.events import DragPayload
from tcgui.widgets.ui import UI

from tgfx import Tgfx2Context
from termin.display._platform_native import (
    SDLBackendWindow,
    poll_sdl_events,
    quit_sdl,
    start_text_input,
)
from termin.editor_tcgui.backend_window_manager import BackendWindowManager
from termin.editor_core.shader_runtime import configure_sdk_shader_runtime


# ---------------------------------------------------------------------------
# Native event dispatch
# ---------------------------------------------------------------------------

def _event_key(value: int) -> Key:
    try:
        return Key(int(value))
    except ValueError:
        log.debug(f"[run_editor] unrecognized native key value={value}")
        return Key.UNKNOWN


def _event_button(value: int) -> MouseButton:
    try:
        return MouseButton(int(value))
    except ValueError:
        log.debug(f"[run_editor] unrecognized native mouse button value={value}")
        return MouseButton.LEFT


def _dispatch_file_drop(event: dict, target_ui: UI) -> bool:
    path_text = event.get("path")
    if not isinstance(path_text, str) or not path_text:
        log.error("[run_editor] file_drop event has empty path")
        return False
    path = Path(path_text)
    payload = DragPayload(
        "project_file",
        {
            "path": str(path),
            "extension": path.suffix.lower(),
            "name": path.name,
        },
    )
    return target_ui.external_drop(
        float(event.get("x", 0.0)),
        float(event.get("y", 0.0)),
        payload,
        int(event.get("mods", 0)),
    )


def _dispatch_native_events(bw: SDLBackendWindow, ui: UI, wm=None) -> tuple[bool, int]:
    """Pump native window events, forward to the UI each event is for.

    We poll native events directly (bypassing BackendWindow.poll_events) because
    the editor wants to route input into the widget tree; BackendWindow
    only cares about quit/close for its own should_close flag. The platform
    event source is drained exactly once per frame.

    When ``wm`` is passed, window-scoped events (mouse, keys, close)
    are routed to the secondary window's UI. Without ``wm`` only the
    main window is served (legacy single-window callers).
    """
    main_id = bw.window_id()
    routed = 0
    for event in poll_sdl_events():
        etype = event.get("type")

        if etype == "quit":
            bw.set_should_close(True)
            return False, routed

        if etype == "window_close":
            wid = int(event.get("window_id", 0))
            if wm is not None and wm.handle_window_close(wid):
                bw.set_should_close(True)
                return False, routed
            if wm is None and wid == main_id:
                bw.set_should_close(True)
                return False, routed
            continue

        wid = int(event.get("window_id", 0))
        target_ui = ui
        if wm is not None and wid:
            # termin.display stores UI in entry.host_data (see
            # BackendWindowManager.register_main / create_window).
            matched = wm.get_entry_for_window_id(wid)
            if matched is not None and matched.host_data is not None:
                target_ui = matched.host_data

        if etype == "mouse_move":
            routed += 1
            target_ui.mouse_move(
                float(event.get("x", 0.0)),
                float(event.get("y", 0.0)),
                int(event.get("mods", 0)),
            )
        elif etype == "mouse_down":
            routed += 1
            target_ui.mouse_down(
                float(event.get("x", 0.0)),
                float(event.get("y", 0.0)),
                _event_button(int(event.get("button", MouseButton.LEFT.value))),
                int(event.get("mods", 0)),
            )
        elif etype == "mouse_up":
            routed += 1
            target_ui.mouse_up(
                float(event.get("x", 0.0)),
                float(event.get("y", 0.0)),
                _event_button(int(event.get("button", MouseButton.LEFT.value))),
                int(event.get("mods", 0)),
            )
        elif etype == "mouse_wheel":
            routed += 1
            target_ui.mouse_wheel(
                float(event.get("dx", 0.0)),
                float(event.get("dy", 0.0)),
                float(event.get("x", 0.0)),
                float(event.get("y", 0.0)),
                int(event.get("mods", 0)),
            )
        elif etype == "key_down":
            routed += 1
            target_ui.key_down(
                _event_key(int(event.get("key", Key.UNKNOWN.value))),
                int(event.get("mods", 0)),
            )
        elif etype == "text_input":
            routed += 1
            target_ui.text_input(str(event.get("text", "")))
        elif etype == "file_drop":
            routed += 1
            _dispatch_file_drop(event, target_ui)

    return True, routed


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def init_editor_tcgui(debug_resource: str | None = None, no_scene: bool = False) -> None:
    """Initialize the tcgui editor and setup engine callbacks.

    Called from C++ before EngineCore.run(). Does NOT call engine.run().
    """
    from termin.bootstrap import bootstrap_editor
    from termin.editor_core.resource_manager import configure_editor_resource_manager_factory
    from termin.engine import EngineCore

    bootstrap_editor()
    configure_editor_resource_manager_factory()
    engine = EngineCore.instance()
    if engine is None:
        raise RuntimeError("EngineCore not created. Must be called from C++ entry point.")

    configure_sdk_shader_runtime("editor")

    # BackendWindow inits SDL and creates its own window + tgfx2 device
    # based on TERMIN_BACKEND. No manual SDL_Init / SDL_GL_CreateContext.
    main_window = SDLBackendWindow("Termin Editor", 1280, 720)
    main_window.maximize()

    # Process-global tgfx2 context owned by the window. Every renderer
    # (UIRenderer, FBOSurface, RenderEngine) wraps the same device+ctx
    # through it.
    tgfx2_ctx = Tgfx2Context.from_window(
        main_window.device_ptr(), main_window.context_ptr())

    # Create initial scene
    from termin.engine import create_scene

    if no_scene:
        initial_scene = None
    else:
        initial_scene = create_scene(name="default")

    ui = UI(graphics=tgfx2_ctx)

    wm = BackendWindowManager()
    wm.register_main(main_window, ui)

    # Apply font size settings before widget tree is built.
    # Widgets read from current_theme in __init__, so this must happen before build().
    from termin.editor_core.settings import EditorSettings
    from tcgui.widgets.theme import current_theme
    settings = EditorSettings.instance()
    current_theme.font_size = settings.get_font_size()
    current_theme.font_size_small = settings.get_font_size_small()

    # Create editor window and build UI
    from termin.editor_tcgui.editor_window import EditorWindowTcgui
    win = EditorWindowTcgui(
        initial_scene=initial_scene,
        scene_manager=engine.scene_manager,
        ctx=tgfx2_ctx,
        main_window=main_window,
    )
    win.build(ui)

    from termin.editor_core.mcp_server import start_editor_mcp_server
    mcp_server = start_editor_mcp_server(win.python_executor)

    # First render
    engine.scene_manager.request_render()
    engine.tick_and_render(0.016)
    wm.render_all()

    start_text_input()

    from tcbase.profiler import Profiler
    profiler = Profiler.instance()

    def poll_events() -> None:
        with profiler.section("Events"):
            keep_running, routed = _dispatch_native_events(main_window, ui, wm)
            if not keep_running:
                win.close()
                return
            if routed > 0:
                engine.scene_manager.request_render()
            if win.process_python_requests() > 0:
                engine.scene_manager.request_render()
            win.poll_file_watcher()

        with profiler.section("Render Compose"):
            wm.render_all()

    def should_continue() -> bool:
        return not (win.should_close() or main_window.should_close())

    def on_shutdown() -> None:
        if mcp_server is not None:
            mcp_server.stop()
        wm.destroy_all()
        quit_sdl()

    engine.set_poll_events_callback(poll_events)
    engine.set_should_continue_callback(should_continue)
    engine.set_on_shutdown_callback(on_shutdown)


def run_editor_tcgui(debug_resource: str | None = None, no_scene: bool = False) -> None:
    """Run the tcgui editor (legacy entry point for C++ callers)."""
    from termin.engine import EngineCore

    engine = EngineCore.instance()
    if engine is None:
        raise RuntimeError(
            "run_editor_tcgui() must be called from C++ entry point. "
            "EngineCore is created in C++."
        )

    init_editor_tcgui(debug_resource=debug_resource, no_scene=no_scene)
    engine.run()
