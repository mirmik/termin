"""tcgui overlay file dialogs example (SDL2 backend).

Demonstrates:
- show_open_file_dialog
- show_save_file_dialog
- show_open_directory_dialog

Requirements: tcbase, tgfx, tcgui, PySDL2
Run: python3 examples/sdl_file_dialogs.py
"""

import ctypes
import sdl2
from sdl2 import video

from tgfx import OpenGLGraphicsBackend
from tcbase import Key, MouseButton, Mods

from tcgui.widgets.ui import UI
from tcgui.widgets.basic import Label, Button
from tcgui.widgets.containers import VStack, Panel
from tcgui.widgets.status_bar import StatusBar
from tcgui.widgets.units import px, pct
from tcgui.widgets.file_dialog_overlay import (
    show_open_file_dialog,
    show_save_file_dialog,
    show_open_directory_dialog,
)


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


def build_ui(graphics):
    root = VStack()
    root.preferred_width = pct(100)
    root.preferred_height = pct(100)
    root.spacing = 0

    content = Panel()
    content.stretch = True
    content.padding = 20
    content.background_color = (0.12, 0.12, 0.14, 1.0)

    stack = VStack()
    stack.spacing = 12
    stack.alignment = "left"

    title = Label()
    title.text = "tcgui File Dialogs Example"
    title.font_size = 24
    title.text_color = (1.0, 1.0, 1.0, 1.0)

    hint = Label()
    hint.text = "Dialogs are rendered in tcgui overlay layer with places, path bar, and filters."
    hint.font_size = 14
    hint.text_color = (0.7, 0.7, 0.75, 1.0)

    selection = Label()
    selection.text = "Selected: (none)"
    selection.font_size = 15
    selection.text_color = (0.9, 0.9, 0.9, 1.0)

    status = StatusBar()
    status.text = "Ready"

    ui = UI(graphics)

    def set_result(kind: str, path: str | None):
        if path:
            selection.text = f"Selected: {path}"
            status.show_message(f"{kind}: {path}", timeout_ms=5000)
        else:
            status.show_message(f"{kind}: cancelled", timeout_ms=2500)

    def on_open_file():
        show_open_file_dialog(
            ui,
            lambda path: set_result("Open File", path),
            title="Open File",
            directory="~",
            filter_str="Images | *.png *.jpg *.jpeg *.bmp;;All files | *.*",
        )

    def on_save_file():
        show_save_file_dialog(
            ui,
            lambda path: set_result("Save File", path),
            title="Save File As",
            directory="~",
            filter_str="Text | *.txt;;JSON | *.json;;All files | *.*",
        )

    def on_open_dir():
        show_open_directory_dialog(
            ui,
            lambda path: set_result("Open Directory", path),
            title="Open Directory",
            directory="~",
        )

    btn_open = Button()
    btn_open.text = "Open File..."
    btn_open.preferred_width = px(220)
    btn_open.preferred_height = px(36)
    btn_open.on_click = on_open_file

    btn_save = Button()
    btn_save.text = "Save File..."
    btn_save.preferred_width = px(220)
    btn_save.preferred_height = px(36)
    btn_save.on_click = on_save_file

    btn_dir = Button()
    btn_dir.text = "Open Directory..."
    btn_dir.preferred_width = px(220)
    btn_dir.preferred_height = px(36)
    btn_dir.on_click = on_open_dir

    stack.add_child(title)
    stack.add_child(hint)
    stack.add_child(btn_open)
    stack.add_child(btn_save)
    stack.add_child(btn_dir)
    stack.add_child(selection)
    content.add_child(stack)

    root.add_child(content)
    root.add_child(status)
    ui.root = root
    return ui


def main():
    window, gl_ctx = create_window("tcgui File Dialogs", 900, 520)

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
            ui.mouse_down(
                float(ev.button.x),
                float(ev.button.y),
                translate_button(ev.button.button),
                translate_mods(sdl2.SDL_GetModState()),
            )
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

        ui.process_deferred()

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
