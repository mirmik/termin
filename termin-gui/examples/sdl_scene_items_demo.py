"""Scene items demo.

Demonstrates the lightweight graphics-item scene API:
- left click: select item
- left drag: move selected item
- middle drag: pan
- wheel: zoom
- Delete: remove selected item
"""

from __future__ import annotations

import ctypes

import sdl2

from tcbase import Key, Mods, MouseButton
from tcgui.scene import GraphicsScene, RectItem, SceneView
from tcgui.widgets.ui import UI
from tcgui.widgets.units import pct
from tcgui.widgets.vstack import VStack
from termin.display import SDLBackendWindow
from tgfx import Tgfx2Context


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


def translate_key(scancode: int) -> int:
    if scancode in _KEY_MAP:
        return _KEY_MAP[scancode]
    keycode = sdl2.SDL_GetKeyFromScancode(scancode)
    if ord('a') <= keycode <= ord('z'):
        keycode -= 32
    if 0 <= keycode < 128:
        try:
            return Key(keycode)
        except ValueError:
            pass
    return Key.UNKNOWN


def translate_mods(sdl_mods: int) -> int:
    result = 0
    if sdl_mods & (sdl2.KMOD_LSHIFT | sdl2.KMOD_RSHIFT):
        result |= Mods.SHIFT.value
    if sdl_mods & (sdl2.KMOD_LCTRL | sdl2.KMOD_RCTRL):
        result |= Mods.CTRL.value
    if sdl_mods & (sdl2.KMOD_LALT | sdl2.KMOD_RALT):
        result |= Mods.ALT.value
    return result


_SDL_BUTTON_MAP = {
    1: MouseButton.LEFT,
    2: MouseButton.MIDDLE,
    3: MouseButton.RIGHT,
}


def translate_button(sdl_button: int) -> MouseButton:
    return _SDL_BUTTON_MAP.get(sdl_button, MouseButton.LEFT)


def build_scene() -> GraphicsScene:
    scene = GraphicsScene()

    a = RectItem("Pass: Color")
    a.x = -200
    a.y = -60
    a.width = 180
    a.height = 90
    a.draggable = True
    a.fill_color = (0.19, 0.28, 0.36, 1.0)
    scene.add_item(a)

    b = RectItem("Pass: Bloom")
    b.x = 40
    b.y = 0
    b.width = 170
    b.height = 90
    b.draggable = True
    b.fill_color = (0.30, 0.22, 0.18, 1.0)
    scene.add_item(b)

    c = RectItem("Resource: GBuffer")
    c.x = -90
    c.y = -220
    c.width = 220
    c.height = 80
    c.draggable = True
    c.fill_color = (0.20, 0.24, 0.18, 1.0)
    scene.add_item(c)

    return scene


def build_ui(graphics) -> UI:
    root = VStack()
    root.preferred_width = pct(100)
    root.preferred_height = pct(100)
    root.spacing = 0

    view = SceneView(build_scene())
    view.preferred_width = pct(100)
    view.preferred_height = pct(100)
    view.offset_x = 500
    view.offset_y = 320

    root.add_child(view)

    ui = UI(graphics=graphics)
    ui.root = root
    return ui


def main():
    window = SDLBackendWindow("tcgui scene items demo", 1200, 800)
    graphics = Tgfx2Context.from_window(window.device_ptr(), window.context_ptr())
    try:
        ui = build_ui(graphics)
        event = sdl2.SDL_Event()
        running = True

        while running:
            while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
                et = event.type
                if et == sdl2.SDL_QUIT:
                    running = False
                    break
                elif et == sdl2.SDL_WINDOWEVENT:
                    if event.window.event == sdl2.SDL_WINDOWEVENT_CLOSE:
                        running = False
                        break
                elif et == sdl2.SDL_MOUSEMOTION:
                    ui.mouse_move(event.motion.x, event.motion.y)
                elif et == sdl2.SDL_MOUSEBUTTONDOWN:
                    ui.mouse_down(
                        event.button.x,
                        event.button.y,
                        translate_button(event.button.button),
                        translate_mods(sdl2.SDL_GetModState()),
                    )
                elif et == sdl2.SDL_MOUSEBUTTONUP:
                    ui.mouse_up(
                        event.button.x,
                        event.button.y,
                        translate_button(event.button.button),
                        translate_mods(sdl2.SDL_GetModState()),
                    )
                elif et == sdl2.SDL_MOUSEWHEEL:
                    mx, my = ctypes.c_int(), ctypes.c_int()
                    sdl2.SDL_GetMouseState(ctypes.byref(mx), ctypes.byref(my))
                    ui.mouse_wheel(event.wheel.x, event.wheel.y, mx.value, my.value)
                elif et == sdl2.SDL_KEYDOWN:
                    key = translate_key(event.key.keysym.scancode)
                    if key == Key.ESCAPE:
                        running = False
                        break
                    ui.key_down(key, translate_mods(sdl2.SDL_GetModState()))
                elif et == sdl2.SDL_TEXTINPUT:
                    ui.text_input(event.text.text.decode("utf-8"))

            ui.process_deferred()

            w, h = window.framebuffer_size()
            tex = ui.render_compose(w, h, background_color=(0.08, 0.08, 0.10, 1.0))
            if tex is not None:
                window.present(tex)
    finally:
        window.close()
        sdl2.SDL_Quit()


if __name__ == "__main__":
    main()
