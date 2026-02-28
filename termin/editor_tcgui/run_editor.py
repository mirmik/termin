"""Entry point for the tcgui-based editor."""

from __future__ import annotations

import ctypes
import sys

import sdl2
from sdl2 import video

from tcbase import Key, log


# ---------------------------------------------------------------------------
# SDL helpers (copied from launcher/app.py)
# ---------------------------------------------------------------------------

def _create_sdl_window(title: str, width: int, height: int):
    """Create fullscreen SDL window with OpenGL 3.3 core context."""
    if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
        raise RuntimeError(f"SDL_Init failed: {sdl2.SDL_GetError()}")

    video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_MAJOR_VERSION, 3)
    video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_MINOR_VERSION, 3)
    video.SDL_GL_SetAttribute(
        video.SDL_GL_CONTEXT_PROFILE_MASK,
        video.SDL_GL_CONTEXT_PROFILE_CORE,
    )
    video.SDL_GL_SetAttribute(video.SDL_GL_DOUBLEBUFFER, 1)
    video.SDL_GL_SetAttribute(video.SDL_GL_DEPTH_SIZE, 24)

    flags = (
        video.SDL_WINDOW_OPENGL
        | video.SDL_WINDOW_RESIZABLE
        | video.SDL_WINDOW_SHOWN
        | video.SDL_WINDOW_MAXIMIZED
    )
    window = video.SDL_CreateWindow(
        title.encode("utf-8"),
        video.SDL_WINDOWPOS_CENTERED,
        video.SDL_WINDOWPOS_CENTERED,
        width, height, flags,
    )
    if not window:
        raise RuntimeError(f"SDL_CreateWindow failed: {sdl2.SDL_GetError()}")

    gl_context = video.SDL_GL_CreateContext(window)
    if not gl_context:
        video.SDL_DestroyWindow(window)
        raise RuntimeError(f"SDL_GL_CreateContext failed: {sdl2.SDL_GetError()}")

    video.SDL_GL_MakeCurrent(window, gl_context)
    video.SDL_GL_SetSwapInterval(1)
    return window, gl_context


def _get_drawable_size(window) -> tuple[int, int]:
    w = ctypes.c_int()
    h = ctypes.c_int()
    video.SDL_GL_GetDrawableSize(window, ctypes.byref(w), ctypes.byref(h))
    return w.value, h.value


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

    # Create SDL window FIRST — GL context must exist before FBO creation
    window, gl_context = _create_sdl_window("Termin Editor", 1280, 720)

    # Setup graphics backend (OpenGL) — must happen after context is current
    from termin.visualization.platform.backends import (
        OpenGLGraphicsBackend,
        set_default_graphics_backend,
    )
    graphics = OpenGLGraphicsBackend.get_instance()
    graphics.ensure_ready()
    set_default_graphics_backend(graphics)

    # Set graphics on RenderingManager so render_all_offscreen works
    from termin._native.render import RenderingManager
    RenderingManager.instance().set_graphics(graphics)

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

    # Create editor window and build UI
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

    sdl2.SDL_StartTextInput()

    # SDL event dispatch → tcgui UI
    def _dispatch_sdl_events() -> bool:
        """Poll SDL events and dispatch to tcgui UI. Returns False on quit."""
        event = sdl2.SDL_Event()
        while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
            etype = event.type
            if etype == sdl2.SDL_QUIT:
                return False
            elif etype == sdl2.SDL_WINDOWEVENT:
                if event.window.event == video.SDL_WINDOWEVENT_CLOSE:
                    return False
            elif etype == sdl2.SDL_MOUSEMOTION:
                ui.mouse_move(float(event.motion.x), float(event.motion.y))
            elif etype == sdl2.SDL_MOUSEBUTTONDOWN:
                from tcbase import MouseButton
                btn_map = {
                    sdl2.SDL_BUTTON_LEFT: MouseButton.LEFT,
                    sdl2.SDL_BUTTON_RIGHT: MouseButton.RIGHT,
                    sdl2.SDL_BUTTON_MIDDLE: MouseButton.MIDDLE,
                }
                btn = btn_map.get(event.button.button, MouseButton.LEFT)
                mods = _translate_sdl_mods(sdl2.SDL_GetModState())
                ui.mouse_down(float(event.button.x), float(event.button.y), btn, mods)
            elif etype == sdl2.SDL_MOUSEBUTTONUP:
                ui.mouse_up(float(event.button.x), float(event.button.y))
            elif etype == sdl2.SDL_MOUSEWHEEL:
                # Get current mouse position for hit testing
                mx = ctypes.c_int()
                my = ctypes.c_int()
                sdl2.SDL_GetMouseState(ctypes.byref(mx), ctypes.byref(my))
                ui.mouse_wheel(float(event.wheel.x), float(event.wheel.y),
                               float(mx.value), float(my.value))
            elif etype == sdl2.SDL_KEYDOWN:
                key = _translate_sdl_key(event.key.keysym.scancode)
                mods = _translate_sdl_mods(event.key.keysym.mod)
                ui.key_down(key, mods)
            elif etype == sdl2.SDL_TEXTINPUT:
                text = event.text.text.decode("utf-8", errors="replace")
                ui.text_input(text)
        return True

    # Setup engine callbacks
    def poll_events() -> None:
        if not _dispatch_sdl_events():
            win.close()
            return

        vw, vh = _get_drawable_size(window)
        graphics.bind_framebuffer(None)
        graphics.set_viewport(0, 0, vw, vh)
        graphics.clear_color_depth(0.08, 0.08, 0.10, 1.0)
        ui.render(vw, vh)
        ui.process_deferred()
        video.SDL_GL_SwapWindow(window)

    def should_continue() -> bool:
        return not win.should_close()

    def on_shutdown() -> None:
        video.SDL_GL_DeleteContext(gl_context)
        video.SDL_DestroyWindow(window)
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
