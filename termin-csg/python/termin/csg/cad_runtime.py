"""Standalone SDL runtime shell for the procedural CSG CAD app."""

from __future__ import annotations

import ctypes

import sdl2

from tcbase import Key, Mods, MouseButton
from tcgui.widgets.ui import UI
from termin.display import SDLBackendWindow
from tgfx import Tgfx2Context

from termin.csg.cad_app import CadApp
from termin.csg.cad_viewer import CsgSceneRenderer


_SDL_BUTTON_MAP = {1: MouseButton.LEFT, 2: MouseButton.MIDDLE, 3: MouseButton.RIGHT}
_KEY_MAP = {
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


def run_cad_app(title: str = "termin-csg CAD", size: tuple[int, int] = (1200, 760)) -> None:
    window = SDLBackendWindow(title, int(size[0]), int(size[1]))
    window.maximize()
    graphics = Tgfx2Context.from_window(window.device_ptr(), window.context_ptr())
    ui = UI(graphics=graphics)
    app = CadApp()
    ui.root = app.build_ui(ui)
    scene_renderer = CsgSceneRenderer(graphics)

    sdl2.SDL_StartTextInput()
    event = sdl2.SDL_Event()
    try:
        while not window.should_close():
            if sdl2.SDL_WaitEventTimeout(ctypes.byref(event), 16):
                _dispatch_event(window, ui, event)
                while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
                    _dispatch_event(window, ui, event)

            width, height = window.framebuffer_size()
            if width <= 0 or height <= 0:
                continue
            if app.dirty:
                app.render_scene(scene_renderer)
            texture = ui.render_compose(width, height, background_color=(0.10, 0.10, 0.12, 1.0))
            ui.process_deferred()
            if texture is not None:
                window.present(texture)
    finally:
        scene_renderer.close()
        window.close()
        sdl2.SDL_Quit()


def _dispatch_event(window, ui: UI, ev) -> None:
    event_type = ev.type
    if event_type == sdl2.SDL_QUIT:
        window.set_should_close(True)
    elif event_type == sdl2.SDL_KEYDOWN:
        key = _translate_key(ev.key.keysym.scancode)
        mods = _translate_mods(sdl2.SDL_GetModState())
        if ui.key_down(key, mods):
            return
        if key == Key.ESCAPE:
            window.set_should_close(True)
    elif event_type == sdl2.SDL_TEXTINPUT:
        ui.text_input(ev.text.text.decode("utf-8"))
    elif event_type == sdl2.SDL_WINDOWEVENT:
        if ev.window.event == sdl2.SDL_WINDOWEVENT_CLOSE:
            window.set_should_close(True)
    elif event_type == sdl2.SDL_MOUSEMOTION:
        ui.mouse_move(float(ev.motion.x), float(ev.motion.y))
    elif event_type == sdl2.SDL_MOUSEBUTTONDOWN:
        ui.mouse_down(
            float(ev.button.x),
            float(ev.button.y),
            _SDL_BUTTON_MAP.get(ev.button.button, MouseButton.LEFT),
            _translate_mods(sdl2.SDL_GetModState()),
        )
    elif event_type == sdl2.SDL_MOUSEBUTTONUP:
        ui.mouse_up(
            float(ev.button.x),
            float(ev.button.y),
            _SDL_BUTTON_MAP.get(ev.button.button, MouseButton.LEFT),
            _translate_mods(sdl2.SDL_GetModState()),
        )
    elif event_type == sdl2.SDL_MOUSEWHEEL:
        mx, my = ctypes.c_int(), ctypes.c_int()
        sdl2.SDL_GetMouseState(ctypes.byref(mx), ctypes.byref(my))
        ui.mouse_wheel(
            float(ev.wheel.x),
            float(ev.wheel.y),
            float(mx.value),
            float(my.value),
            _translate_mods(sdl2.SDL_GetModState()),
        )


def _translate_key(scancode: int) -> Key:
    if scancode in _KEY_MAP:
        return _KEY_MAP[scancode]
    keycode = sdl2.SDL_GetKeyFromScancode(scancode)
    if ord("a") <= keycode <= ord("z"):
        keycode -= 32
    if 0 <= keycode < 128:
        try:
            return Key(keycode)
        except ValueError:
            return Key.UNKNOWN
    return Key.UNKNOWN


def _translate_mods(sdl_mods: int) -> int:
    result = 0
    if sdl_mods & (sdl2.KMOD_LSHIFT | sdl2.KMOD_RSHIFT):
        result |= Mods.SHIFT.value
    if sdl_mods & (sdl2.KMOD_LCTRL | sdl2.KMOD_RCTRL):
        result |= Mods.CTRL.value
    if sdl_mods & (sdl2.KMOD_LALT | sdl2.KMOD_RALT):
        result |= Mods.ALT.value
    return result


__all__ = ["run_cad_app"]
