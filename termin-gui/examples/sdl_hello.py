"""Minimal tcgui + SDL2 example.

Creates an SDL window with OpenGL context and renders a simple UI
with a label, button, and text input.

Requirements: tcbase, tgfx, tcgui, PySDL2
Run: python3 examples/sdl_hello.py
"""

import ctypes
import sdl2
from sdl2 import video

from tgfx import OpenGLGraphicsBackend
from tcbase import Key, MouseButton, Mods

from tcgui.widgets.ui import UI
from tcgui.widgets.basic import Label, Button, TextInput
from tcgui.widgets.containers import VStack, Panel
from tcgui.widgets.units import px, pct


# --- SDL helpers ---

def create_window(title: str, width: int, height: int):
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

    flags = video.SDL_WINDOW_OPENGL | video.SDL_WINDOW_RESIZABLE | video.SDL_WINDOW_SHOWN
    window = video.SDL_CreateWindow(
        title.encode("utf-8"),
        video.SDL_WINDOWPOS_CENTERED,
        video.SDL_WINDOWPOS_CENTERED,
        width, height, flags,
    )
    if not window:
        raise RuntimeError(f"SDL_CreateWindow failed: {sdl2.SDL_GetError()}")

    gl_ctx = video.SDL_GL_CreateContext(window)
    if not gl_ctx:
        video.SDL_DestroyWindow(window)
        raise RuntimeError(f"SDL_GL_CreateContext failed: {sdl2.SDL_GetError()}")

    video.SDL_GL_MakeCurrent(window, gl_ctx)
    video.SDL_GL_SetSwapInterval(1)
    return window, gl_ctx


def get_drawable_size(window):
    w, h = ctypes.c_int(), ctypes.c_int()
    video.SDL_GL_GetDrawableSize(window, ctypes.byref(w), ctypes.byref(h))
    return w.value, h.value


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


# --- UI ---

def build_ui(graphics):
    root = Panel()
    root.preferred_width = pct(100)
    root.preferred_height = pct(100)
    root.background_color = (0.12, 0.12, 0.14, 1.0)
    root.padding = 30

    stack = VStack()
    stack.spacing = 16

    title = Label()
    title.text = "tcgui — SDL2 Example"
    title.font_size = 28
    title.text_color = (1.0, 1.0, 1.0, 1.0)

    counter_label = Label()
    counter_label.text = "Clicks: 0"
    counter_label.font_size = 18
    counter_label.text_color = (0.8, 0.8, 0.8, 1.0)

    count = [0]

    def on_click():
        count[0] += 1
        counter_label.text = f"Clicks: {count[0]}"

    button = Button()
    button.text = "Click me"
    button.preferred_width = px(200)
    button.preferred_height = px(36)
    button.on_click = on_click

    text_input = TextInput()
    text_input.placeholder = "Type something..."
    text_input.preferred_width = px(300)
    text_input.preferred_height = px(32)

    stack.add_child(title)
    stack.add_child(counter_label)
    stack.add_child(button)
    stack.add_child(text_input)
    root.add_child(stack)

    ui = UI(graphics)
    ui.root = root
    return ui


# --- Main ---

def main():
    window, gl_ctx = create_window("tcgui SDL Example", 800, 500)

    graphics = OpenGLGraphicsBackend.get_instance()
    graphics.ensure_ready()

    ui = build_ui(graphics)

    sdl2.SDL_StartTextInput()
    event = sdl2.SDL_Event()
    running = True

    def dispatch(ev):
        nonlocal running
        t = ev.type
        if t == sdl2.SDL_QUIT:
            running = False
        elif t == sdl2.SDL_WINDOWEVENT:
            if ev.window.event == video.SDL_WINDOWEVENT_CLOSE:
                running = False
        elif t == sdl2.SDL_MOUSEMOTION:
            ui.mouse_move(float(ev.motion.x), float(ev.motion.y))
        elif t == sdl2.SDL_MOUSEBUTTONDOWN:
            ui.mouse_down(float(ev.button.x), float(ev.button.y), translate_button(ev.button.button))
        elif t == sdl2.SDL_MOUSEBUTTONUP:
            ui.mouse_up(float(ev.button.x), float(ev.button.y))
        elif t == sdl2.SDL_MOUSEWHEEL:
            mx, my = ctypes.c_int(), ctypes.c_int()
            sdl2.SDL_GetMouseState(ctypes.byref(mx), ctypes.byref(my))
            ui.mouse_wheel(float(ev.wheel.x), float(ev.wheel.y), float(mx.value), float(my.value))
        elif t == sdl2.SDL_KEYDOWN:
            key = translate_key(ev.key.keysym.scancode)
            mods = translate_mods(sdl2.SDL_GetModState())
            ui.key_down(key, mods)
        elif t == sdl2.SDL_TEXTINPUT:
            ui.text_input(ev.text.text.decode("utf-8"))

    while running:
        if sdl2.SDL_WaitEventTimeout(ctypes.byref(event), 500):
            dispatch(event)
            while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
                dispatch(event)

        if not running:
            break

        vw, vh = get_drawable_size(window)
        graphics.bind_framebuffer(None)
        graphics.set_viewport(0, 0, vw, vh)
        graphics.clear_color_depth(0.12, 0.12, 0.14, 1.0)

        ui.render(vw, vh)

        video.SDL_GL_SwapWindow(window)

    video.SDL_GL_DeleteContext(gl_ctx)
    video.SDL_DestroyWindow(window)
    sdl2.SDL_Quit()


if __name__ == "__main__":
    main()
