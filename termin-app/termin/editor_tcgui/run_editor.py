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
from termin.display._platform_native import SDLBackendWindow
from termin.editor_tcgui.backend_window_manager import BackendWindowManager


# ---------------------------------------------------------------------------
# SDL key / mouse translation (unchanged from the SDL-based editor)
# ---------------------------------------------------------------------------

def _translate_sdl_key(scancode: int) -> Key:
    _MAP = {
        sdl2.SDL_SCANCODE_A: Key.A,
        sdl2.SDL_SCANCODE_B: Key.B,
        sdl2.SDL_SCANCODE_C: Key.C,
        sdl2.SDL_SCANCODE_D: Key.D,
        sdl2.SDL_SCANCODE_E: Key.E,
        sdl2.SDL_SCANCODE_F: Key.F,
        sdl2.SDL_SCANCODE_G: Key.G,
        sdl2.SDL_SCANCODE_H: Key.H,
        sdl2.SDL_SCANCODE_I: Key.I,
        sdl2.SDL_SCANCODE_J: Key.J,
        sdl2.SDL_SCANCODE_K: Key.K,
        sdl2.SDL_SCANCODE_L: Key.L,
        sdl2.SDL_SCANCODE_M: Key.M,
        sdl2.SDL_SCANCODE_N: Key.N,
        sdl2.SDL_SCANCODE_O: Key.O,
        sdl2.SDL_SCANCODE_P: Key.P,
        sdl2.SDL_SCANCODE_Q: Key.Q,
        sdl2.SDL_SCANCODE_R: Key.R,
        sdl2.SDL_SCANCODE_S: Key.S,
        sdl2.SDL_SCANCODE_T: Key.T,
        sdl2.SDL_SCANCODE_U: Key.U,
        sdl2.SDL_SCANCODE_V: Key.V,
        sdl2.SDL_SCANCODE_W: Key.W,
        sdl2.SDL_SCANCODE_X: Key.X,
        sdl2.SDL_SCANCODE_Y: Key.Y,
        sdl2.SDL_SCANCODE_Z: Key.Z,
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
    if ord('a') <= keycode <= ord('z'):
        keycode -= 32
    if 0 <= keycode < 128:
        try:
            return Key(keycode)
        except ValueError:
            log.debug(f"[run_editor] unrecognized SDL scancode mapped to keycode={keycode}")
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


def _dispatch_sdl_events(bw: BackendWindow, ui: UI, wm=None, trace: bool = False) -> bool:
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
    total = 0
    routed = 0
    mouse = 0
    keys = 0
    window_events = 0
    while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
        total += 1
        etype = event.type

        if etype == sdl2.SDL_QUIT:
            bw.set_should_close(True)
            return False

        if etype == sdl2.SDL_WINDOWEVENT:
            window_events += 1
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
            mouse += 1
            routed += 1
            if trace:
                log.info(
                    f"[tcgui-events] mouse_motion wid={wid} target={id(target_ui)} "
                    f"x={event.motion.x} y={event.motion.y}")
            target_ui.mouse_move(float(event.motion.x), float(event.motion.y))
        elif etype == sdl2.SDL_MOUSEBUTTONDOWN:
            mouse += 1
            routed += 1
            btn = _BTN_MAP.get(event.button.button, MouseButton.LEFT)
            mods = _translate_sdl_mods(sdl2.SDL_GetModState())
            if trace:
                log.info(
                    f"[tcgui-events] mouse_down wid={wid} target={id(target_ui)} "
                    f"button={event.button.button} x={event.button.x} y={event.button.y}")
            target_ui.mouse_down(float(event.button.x), float(event.button.y), btn, mods)
        elif etype == sdl2.SDL_MOUSEBUTTONUP:
            mouse += 1
            routed += 1
            btn = _BTN_MAP.get(event.button.button, MouseButton.LEFT)
            mods = _translate_sdl_mods(sdl2.SDL_GetModState())
            if trace:
                log.info(
                    f"[tcgui-events] mouse_up wid={wid} target={id(target_ui)} "
                    f"button={event.button.button} x={event.button.x} y={event.button.y}")
            target_ui.mouse_up(float(event.button.x), float(event.button.y), btn, mods)
        elif etype == sdl2.SDL_MOUSEWHEEL:
            mouse += 1
            routed += 1
            mx = ctypes.c_int()
            my = ctypes.c_int()
            sdl2.SDL_GetMouseState(ctypes.byref(mx), ctypes.byref(my))
            mods = _translate_sdl_mods(sdl2.SDL_GetModState())
            target_ui.mouse_wheel(float(event.wheel.x), float(event.wheel.y),
                                  float(mx.value), float(my.value), mods)
        elif etype == sdl2.SDL_KEYDOWN:
            keys += 1
            routed += 1
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
        elif etype == sdl2.SDL_KEYUP:
            keys += 1
        elif etype == sdl2.SDL_TEXTINPUT:
            keys += 1
            routed += 1
            text = event.text.text.decode("utf-8", errors="replace")
            target_ui.text_input(text)

    if trace or total > 0:
        log.info(
            f"[tcgui-events] poll total={total} routed={routed} "
            f"mouse={mouse} keys={keys} window={window_events} main_id={main_id}")
    _dispatch_sdl_events.last_routed = routed
    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def init_editor_tcgui(debug_resource: str | None = None, no_scene: bool = False) -> None:
    """Initialize the tcgui editor and setup engine callbacks.

    Called from C++ before EngineCore.run(). Does NOT call engine.run().
    """
    from termin.engine import EngineCore

    log.info("[tcgui-startup] init_editor_tcgui: begin")
    engine = EngineCore.instance()
    if engine is None:
        raise RuntimeError("EngineCore not created. Must be called from C++ entry point.")
    log.info("[tcgui-startup] EngineCore acquired")

    # BackendWindow inits SDL and creates its own window + tgfx2 device
    # based on TERMIN_BACKEND. No manual SDL_Init / SDL_GL_CreateContext.
    main_window = SDLBackendWindow("Termin Editor", 1280, 720)
    log.info(
        f"[tcgui-startup] main window created "
        f"fb={main_window.framebuffer_size()} "
        f"window_id={main_window.window_id()}")
    main_window.maximize()
    log.info(f"[tcgui-startup] main window maximized fb={main_window.framebuffer_size()}")

    # Process-global tgfx2 context owned by the window. Every renderer
    # (UIRenderer, FBOSurface, RenderEngine) wraps the same device+ctx
    # through it.
    tgfx2_ctx = Tgfx2Context.from_window(
        main_window.device_ptr(), main_window.context_ptr())
    log.info("[tcgui-startup] Tgfx2Context.from_window done")

    # Create world and scene
    from termin.visualization.core.world import World
    from termin.visualization.core.scene import create_scene

    world = World()
    if no_scene:
        initial_scene = None
    else:
        initial_scene = create_scene(name="default")
        world.add_scene(initial_scene)
    log.info(f"[tcgui-startup] world/scene ready no_scene={no_scene}")

    ui = UI(graphics=tgfx2_ctx)
    log.info("[tcgui-startup] UI created")

    wm = BackendWindowManager()
    wm.register_main(main_window, ui)
    log.info("[tcgui-startup] BackendWindowManager registered main")

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
        world=world,
        initial_scene=initial_scene,
        scene_manager=engine.scene_manager,
        offscreen_context=None,
        ctx=tgfx2_ctx,
        main_window=main_window,
    )
    log.info("[tcgui-startup] EditorWindowTcgui constructed")
    win.build(ui)
    log.info("[tcgui-startup] UI build done")

    # First render
    engine.scene_manager.request_render()
    log.info("[tcgui-startup] first tick_and_render: begin")
    engine.tick_and_render(0.016)
    log.info("[tcgui-startup] first tick_and_render: end")
    log.info("[tcgui-startup] first wm.render_all: begin")
    wm.render_all()
    log.info("[tcgui-startup] first wm.render_all: end")

    sdl2.SDL_StartTextInput()

    from termin.core.profiler import Profiler
    profiler = Profiler.instance()

    poll_frame = 0

    def poll_events() -> None:
        nonlocal poll_frame
        poll_frame += 1
        trace = poll_frame <= 20 or poll_frame % 120 == 0
        if trace:
            log.info(f"[tcgui-loop] frame={poll_frame}: poll begin")
        with profiler.section("Events"):
            if not _dispatch_sdl_events(main_window, ui, wm, trace=trace):
                win.close()
                return
            if getattr(_dispatch_sdl_events, "last_routed", 0) > 0:
                engine.scene_manager.request_render()
            win.poll_file_watcher()
        if trace:
            log.info(f"[tcgui-loop] frame={poll_frame}: events end")

        with profiler.section("Render Compose"):
            if trace:
                log.info(f"[tcgui-loop] frame={poll_frame}: wm.render_all begin")
            wm.render_all()
            if trace:
                log.info(f"[tcgui-loop] frame={poll_frame}: wm.render_all end")

    def should_continue() -> bool:
        return not (win.should_close() or main_window.should_close())

    def on_shutdown() -> None:
        wm.destroy_all()
        sdl2.SDL_Quit()

    log.info(
        "[tcgui-startup] configuring EngineCore callbacks "
        f"engine={engine} type={type(engine)}")
    log.info(
        "[tcgui-startup] callback attrs "
        f"poll={getattr(engine, 'set_poll_events_callback', None)} "
        f"continue={getattr(engine, 'set_should_continue_callback', None)} "
        f"shutdown={getattr(engine, 'set_on_shutdown_callback', None)}")
    log.info("[tcgui-startup] set_poll_events_callback begin")
    engine.set_poll_events_callback(poll_events)
    log.info("[tcgui-startup] set_poll_events_callback end")
    log.info("[tcgui-startup] set_should_continue_callback begin")
    engine.set_should_continue_callback(should_continue)
    log.info("[tcgui-startup] set_should_continue_callback end")
    log.info("[tcgui-startup] set_on_shutdown_callback begin")
    engine.set_on_shutdown_callback(on_shutdown)
    log.info("[tcgui-startup] set_on_shutdown_callback end")


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
