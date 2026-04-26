"""Entry point for the tcgui-based editor.

Runs on ``termin.display.BackendWindow`` — backend selection lives in
the env-var ``TERMIN_BACKEND`` (``opengl`` / ``vulkan``). No raw SDL+GL
window creation, no per-window tc_gpu_context, no SDL_GL_SHARE_WITH_
CURRENT_CONTEXT: the process owns a single tgfx2 IRenderDevice (borrowed
from the BackendWindow) and every renderer — UIRenderer, FBOSurface,
RenderEngine — lives on it.
"""

from __future__ import annotations

import ctypes

import sdl2
from sdl2 import video

from tcbase import Key, MouseButton, log
from tcgui.widgets.ui import UI

from tgfx import Tgfx2Context
from termin.display._platform_native import BackendWindow
from termin.editor_tcgui.backend_window_manager import BackendWindowManager


# ---------------------------------------------------------------------------
# SDL key / mouse translation (unchanged from the SDL-based editor)
# ---------------------------------------------------------------------------

def _translate_sdl_key(scancode: int) -> Key:
    _MAP = {
        sdl2.SDL_SCANCODE_BACKSPACE: Key.BACKSPACE,
        sdl2.SDL_SCANCODE_DELETE: Key.DELETE,
        sdl2.SDL_SCANCODE_LEFT: Key.LEFT,
        sdl2.SDL_SCANCODE_RIGHT: Key.RIGHT,
        sdl2.SDL_SCANCODE_UP: Key.UP,
        sdl2.SDL_SCANCODE_DOWN: Key.DOWN,
        sdl2.SDL_SCANCODE_HOME: Key.HOME,
        sdl2.SDL_SCANCODE_END: Key.END,
        sdl2.SDL_SCANCODE_RETURN: Key.ENTER,
        sdl2.SDL_SCANCODE_ESCAPE: Key.ESCAPE,
        sdl2.SDL_SCANCODE_TAB: Key.TAB,
        sdl2.SDL_SCANCODE_SPACE: Key.SPACE,
    }
    if scancode in _MAP:
        return _MAP[scancode]
    keycode = sdl2.SDL_GetKeyFromScancode(scancode)
    if 0 <= keycode < 128:
        try:
            return Key(keycode)
        except ValueError:
            pass
    return Key.UNKNOWN


def _translate_sdl_mods(sdl_mods: int) -> int:
    result = 0
    if sdl_mods & (sdl2.KMOD_LSHIFT | sdl2.KMOD_RSHIFT):
        result |= 0x0001
    if sdl_mods & (sdl2.KMOD_LCTRL | sdl2.KMOD_RCTRL):
        result |= 0x0002
    if sdl_mods & (sdl2.KMOD_LALT | sdl2.KMOD_RALT):
        result |= 0x0004
    return result


_BTN_MAP = {
    sdl2.SDL_BUTTON_LEFT: MouseButton.LEFT,
    sdl2.SDL_BUTTON_RIGHT: MouseButton.RIGHT,
    sdl2.SDL_BUTTON_MIDDLE: MouseButton.MIDDLE,
}


# ---------------------------------------------------------------------------
# SDL event dispatch
# ---------------------------------------------------------------------------

def _get_event_window_id(event) -> int | None:
    etype = event.type
    if etype in (sdl2.SDL_MOUSEMOTION,):
        return event.motion.windowID
    if etype in (sdl2.SDL_MOUSEBUTTONDOWN, sdl2.SDL_MOUSEBUTTONUP):
        return event.button.windowID
    if etype in (sdl2.SDL_MOUSEWHEEL,):
        return event.wheel.windowID
    if etype in (sdl2.SDL_KEYDOWN, sdl2.SDL_KEYUP):
        return event.key.windowID
    if etype == sdl2.SDL_TEXTINPUT:
        return event.text.windowID
    return None


def _dispatch_sdl_events(bw: BackendWindow, ui: UI, wm=None) -> bool:
    """Pump SDL events, forward to the UI of the window each event is for.

    We poll SDL directly (bypassing BackendWindow.poll_events) because
    the editor wants to route input into the widget tree; BackendWindow
    only cares about quit/close for its own should_close flag. Single
    SDL source is drained exactly once per frame.

    When ``wm`` is passed, window-scoped events (mouse, keys, close)
    are routed to the secondary window's UI. Without ``wm`` only the
    main window is served (legacy single-window callers).
    """
    event = sdl2.SDL_Event()
    main_id = bw.window_id()
    while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
        etype = event.type

        if etype == sdl2.SDL_QUIT:
            bw.set_should_close(True)
            return False

        if etype == sdl2.SDL_WINDOWEVENT:
            if event.window.event == video.SDL_WINDOWEVENT_CLOSE:
                wid = event.window.windowID
                if wm is not None and wm.handle_window_close(wid):
                    bw.set_should_close(True)
                    return False
                if wm is None and wid == main_id:
                    bw.set_should_close(True)
                    return False
            continue

        wid = _get_event_window_id(event)
        target_ui = ui
        if wm is not None and wid is not None:
            # termin.display stores UI in entry.host_data (see
            # BackendWindowManager.register_main / create_window).
            matched = wm.get_entry_for_window_id(wid)
            if matched is not None and matched.host_data is not None:
                target_ui = matched.host_data

        if etype == sdl2.SDL_MOUSEMOTION:
            target_ui.mouse_move(float(event.motion.x), float(event.motion.y))
        elif etype == sdl2.SDL_MOUSEBUTTONDOWN:
            btn = _BTN_MAP.get(event.button.button, MouseButton.LEFT)
            mods = _translate_sdl_mods(sdl2.SDL_GetModState())
            target_ui.mouse_down(float(event.button.x), float(event.button.y), btn, mods)
        elif etype == sdl2.SDL_MOUSEBUTTONUP:
            btn = _BTN_MAP.get(event.button.button, MouseButton.LEFT)
            mods = _translate_sdl_mods(sdl2.SDL_GetModState())
            target_ui.mouse_up(float(event.button.x), float(event.button.y), btn, mods)
        elif etype == sdl2.SDL_MOUSEWHEEL:
            mx = ctypes.c_int()
            my = ctypes.c_int()
            sdl2.SDL_GetMouseState(ctypes.byref(mx), ctypes.byref(my))
            target_ui.mouse_wheel(float(event.wheel.x), float(event.wheel.y),
                                  float(mx.value), float(my.value))
        elif etype == sdl2.SDL_KEYDOWN:
            key = _translate_sdl_key(event.key.keysym.scancode)
            mods = _translate_sdl_mods(event.key.keysym.mod)
            target_ui.key_down(key, mods)
            # ESC closes the event's window — not always the main one.
            if key == Key.ESCAPE:
                if wid is None or wid == main_id or wm is None:
                    bw.set_should_close(True)
                    return False
                if wm is not None and wm.handle_window_close(wid):
                    bw.set_should_close(True)
                    return False
        elif etype == sdl2.SDL_TEXTINPUT:
            text = event.text.text.decode("utf-8", errors="replace")
            target_ui.text_input(text)

    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def init_editor_tcgui(debug_resource: str | None = None, no_scene: bool = False) -> None:
    """Initialize the tcgui editor and setup engine callbacks.

    Called from C++ before EngineCore.run(). Does NOT call engine.run().
    """
    from termin._native import EngineCore

    engine = EngineCore.instance()
    if engine is None:
        raise RuntimeError("EngineCore not created. Must be called from C++ entry point.")

    # BackendWindow inits SDL and creates its own window + tgfx2 device
    # based on TERMIN_BACKEND. No manual SDL_Init / SDL_GL_CreateContext.
    main_window = BackendWindow("Termin Editor", 1280, 720)

    # Process-global tgfx2 context owned by the window. Every renderer
    # (UIRenderer, FBOSurface, RenderEngine) wraps the same device+ctx
    # through it.
    tgfx2_ctx = Tgfx2Context.from_window(
        main_window.device_ptr(), main_window.context_ptr())

    # Create world and scene
    from termin.visualization.core.world import World
    from termin.visualization.core.scene import create_scene

    world = World()
    if no_scene:
        initial_scene = None
    else:
        initial_scene = create_scene(name="default")
        world.add_scene(initial_scene)

    ui = UI(graphics=tgfx2_ctx)

    wm = BackendWindowManager()
    wm.register_main(main_window, ui)

    # Apply font size settings before widget tree is built.
    # Widgets read from current_theme in __init__, so this must happen before build().
    from termin.editor.settings import EditorSettings
    from tcgui.widgets.theme import current_theme
    settings = EditorSettings.instance()
    current_theme.font_size = settings.get_font_size()
    current_theme.font_size_small = settings.get_font_size_small()

    # Create editor window and build UI
    from termin.editor_tcgui.editor_window import EditorWindowTcgui
    win = EditorWindowTcgui(
        world=world,
        initial_scene=initial_scene,
        scene_manager=engine.scene_manager,
        offscreen_context=None,
        ctx=tgfx2_ctx,
    )
    win.build(ui)

    # First render
    engine.scene_manager.request_render()
    engine.tick_and_render(0.016)

    sdl2.SDL_StartTextInput()

    from termin.core.profiler import Profiler
    profiler = Profiler.instance()

    def poll_events() -> None:
        with profiler.section("Events"):
            if not _dispatch_sdl_events(main_window, ui, wm):
                win.close()
                return
            win.poll_file_watcher()

        with profiler.section("Render Compose"):
            wm.render_all()

    def should_continue() -> bool:
        return not (win.should_close() or main_window.should_close())

    def on_shutdown() -> None:
        wm.destroy_all()
        sdl2.SDL_Quit()

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
