"""Multi-window example — open widgets in separate windows via UI.create_window.

Demonstrates:
- UI.create_window callback for creating secondary windows
- UI.on_empty for auto-closing empty windows
- Event routing by SDL windowID
- All windows rendered equally in a single loop

Requirements: tcbase, tgfx, tcgui, PySDL2
Run: python3 examples/sdl_multiwindow.py
"""

import ctypes
from dataclasses import dataclass
from typing import Any

import sdl2
from sdl2 import video

from tgfx import OpenGLGraphicsBackend
from tcbase import Key, MouseButton, Mods

from tcgui.widgets.ui import UI
from tcgui.widgets.basic import Label, Button, TextInput, SpinBox
from tcgui.widgets.containers import VStack, HStack, Panel
from tcgui.widgets.dialog import Dialog
from tcgui.widgets.units import px, pct


# ---------------------------------------------------------------------------
# SDL helpers (same as sdl_hello.py)
# ---------------------------------------------------------------------------

def _create_sdl_window(title: str, width: int, height: int,
                       maximized: bool = False):
    flags = video.SDL_WINDOW_OPENGL | video.SDL_WINDOW_RESIZABLE | video.SDL_WINDOW_SHOWN
    if maximized:
        flags |= video.SDL_WINDOW_MAXIMIZED
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


def _get_drawable_size(window):
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

_BTN_MAP = {1: MouseButton.LEFT, 2: MouseButton.MIDDLE, 3: MouseButton.RIGHT}


def _translate_key(scancode):
    if scancode in _KEY_MAP:
        return _KEY_MAP[scancode]
    keycode = sdl2.SDL_GetKeyFromScancode(scancode)
    if 0 <= keycode < 128:
        try:
            return Key(keycode)
        except ValueError:
            pass
    return Key.UNKNOWN


def _translate_mods(sdl_mods):
    result = 0
    if sdl_mods & (sdl2.KMOD_LSHIFT | sdl2.KMOD_RSHIFT):
        result |= Mods.SHIFT.value
    if sdl_mods & (sdl2.KMOD_LCTRL | sdl2.KMOD_RCTRL):
        result |= Mods.CTRL.value
    if sdl_mods & (sdl2.KMOD_LALT | sdl2.KMOD_RALT):
        result |= Mods.ALT.value
    return result


# ---------------------------------------------------------------------------
# Minimal window manager (inline for the example)
# ---------------------------------------------------------------------------

@dataclass
class _WinEntry:
    sdl_window: Any
    gl_context: Any
    ui: UI
    is_main: bool = False


class _WindowManager:
    def __init__(self, graphics):
        self._graphics = graphics
        self._windows: list[_WinEntry] = []

    def register_main(self, sdl_window, gl_context, ui):
        entry = _WinEntry(sdl_window, gl_context, ui, is_main=True)
        self._windows.append(entry)
        ui.create_window = self.create_window

    def create_window(self, title: str, width: int, height: int) -> UI | None:
        video.SDL_GL_SetAttribute(video.SDL_GL_SHARE_WITH_CURRENT_CONTEXT, 1)
        sdl_win, gl_ctx = _create_sdl_window(title, width, height)
        # Restore previous context
        if self._windows:
            prev = self._windows[0]
            video.SDL_GL_MakeCurrent(prev.sdl_window, prev.gl_context)

        window_ui = UI(graphics=self._graphics)
        entry = _WinEntry(sdl_win, gl_ctx, window_ui)
        self._windows.append(entry)

        def _destroy():
            if entry in self._windows:
                self._windows.remove(entry)
                video.SDL_GL_DeleteContext(entry.gl_context)
                video.SDL_DestroyWindow(entry.sdl_window)

        window_ui.close_window = _destroy
        window_ui.on_empty = _destroy
        window_ui.create_window = self.create_window
        return window_ui

    def get_ui_for_window_id(self, wid):
        for e in self._windows:
            if video.SDL_GetWindowID(e.sdl_window) == wid:
                return e.ui
        return None

    def handle_window_close(self, wid) -> bool:
        for e in self._windows:
            if video.SDL_GetWindowID(e.sdl_window) == wid:
                if e.is_main:
                    return True
                if e.ui.close_window:
                    e.ui.close_window()
                return False
        return False

    def render_all(self):
        for e in list(self._windows):
            video.SDL_GL_MakeCurrent(e.sdl_window, e.gl_context)
            vw, vh = _get_drawable_size(e.sdl_window)
            self._graphics.bind_framebuffer(None)
            self._graphics.set_viewport(0, 0, vw, vh)
            self._graphics.clear_color_depth(0.12, 0.12, 0.14, 1.0)
            e.ui.render(vw, vh)
            e.ui.process_deferred()
            video.SDL_GL_SwapWindow(e.sdl_window)

    def destroy_all(self):
        for e in list(self._windows):
            video.SDL_GL_DeleteContext(e.gl_context)
            video.SDL_DestroyWindow(e.sdl_window)
        self._windows.clear()


# ---------------------------------------------------------------------------
# Event dispatch
# ---------------------------------------------------------------------------

def _get_event_window_id(event):
    t = event.type
    if t == sdl2.SDL_MOUSEMOTION:
        return event.motion.windowID
    if t in (sdl2.SDL_MOUSEBUTTONDOWN, sdl2.SDL_MOUSEBUTTONUP):
        return event.button.windowID
    if t == sdl2.SDL_MOUSEWHEEL:
        return event.wheel.windowID
    if t in (sdl2.SDL_KEYDOWN, sdl2.SDL_KEYUP):
        return event.key.windowID
    if t == sdl2.SDL_TEXTINPUT:
        return event.text.windowID
    return None


def dispatch_events(wm: _WindowManager) -> bool:
    event = sdl2.SDL_Event()
    while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
        t = event.type

        if t == sdl2.SDL_QUIT:
            return False

        if t == sdl2.SDL_WINDOWEVENT:
            if event.window.event == video.SDL_WINDOWEVENT_CLOSE:
                if wm.handle_window_close(event.window.windowID):
                    return False
            continue

        wid = _get_event_window_id(event)
        if wid is None:
            continue
        ui = wm.get_ui_for_window_id(wid)
        if ui is None:
            continue

        if t == sdl2.SDL_MOUSEMOTION:
            ui.mouse_move(float(event.motion.x), float(event.motion.y))
        elif t == sdl2.SDL_MOUSEBUTTONDOWN:
            btn = _BTN_MAP.get(event.button.button, MouseButton.LEFT)
            mods = _translate_mods(sdl2.SDL_GetModState())
            ui.mouse_down(float(event.button.x), float(event.button.y),
                          btn, mods)
        elif t == sdl2.SDL_MOUSEBUTTONUP:
            btn = _BTN_MAP.get(event.button.button, MouseButton.LEFT)
            mods = _translate_mods(sdl2.SDL_GetModState())
            ui.mouse_up(float(event.button.x), float(event.button.y),
                        btn, mods)
        elif t == sdl2.SDL_MOUSEWHEEL:
            mx, my = ctypes.c_int(), ctypes.c_int()
            sdl2.SDL_GetMouseState(ctypes.byref(mx), ctypes.byref(my))
            ui.mouse_wheel(float(event.wheel.x), float(event.wheel.y),
                           float(mx.value), float(my.value))
        elif t == sdl2.SDL_KEYDOWN:
            key = _translate_key(event.key.keysym.scancode)
            mods = _translate_mods(event.key.keysym.mod)
            ui.key_down(key, mods)
        elif t == sdl2.SDL_TEXTINPUT:
            text = event.text.text.decode("utf-8", errors="replace")
            ui.text_input(text)

    return True


# ---------------------------------------------------------------------------
# UI setup
# ---------------------------------------------------------------------------

def build_main_ui(graphics, wm):
    root = Panel()
    root.preferred_width = pct(100)
    root.preferred_height = pct(100)
    root.background_color = (0.12, 0.12, 0.14, 1.0)
    root.padding = 30

    stack = VStack()
    stack.spacing = 16

    title = Label()
    title.text = "Multi-Window Example"
    title.font_size = 28
    title.text_color = (1.0, 1.0, 1.0, 1.0)
    stack.add_child(title)

    subtitle = Label()
    subtitle.text = "Click buttons below to open widgets in separate windows"
    subtitle.font_size = 14
    subtitle.text_color = (0.6, 0.6, 0.6, 1.0)
    stack.add_child(subtitle)

    ui = UI(graphics)

    # --- Button: open a simple widget in a window ---
    btn_widget = Button()
    btn_widget.text = "Open Widget in Window"
    btn_widget.preferred_width = px(250)
    btn_widget.preferred_height = px(36)

    counter = [0]

    def _open_widget_window():
        counter[0] += 1
        window_ui = ui.create_window(
            f"Widget Window #{counter[0]}", 400, 300)
        if window_ui is None:
            return

        panel = Panel()
        panel.preferred_width = pct(100)
        panel.preferred_height = pct(100)
        panel.background_color = (0.15, 0.15, 0.18, 1.0)
        panel.padding = 20

        inner = VStack()
        inner.spacing = 12

        lbl = Label()
        lbl.text = f"Window #{counter[0]}"
        lbl.font_size = 22
        lbl.text_color = (1.0, 1.0, 1.0, 1.0)
        inner.add_child(lbl)

        inp = TextInput()
        inp.placeholder = "Type here..."
        inp.preferred_width = px(250)
        inner.add_child(inp)

        click_count = [0]
        click_lbl = Label()
        click_lbl.text = "Clicks: 0"
        click_lbl.text_color = (0.8, 0.8, 0.8, 1.0)
        inner.add_child(click_lbl)

        click_btn = Button()
        click_btn.text = "Click me"
        click_btn.preferred_width = px(120)
        click_btn.preferred_height = px(32)

        def _on_click():
            click_count[0] += 1
            click_lbl.text = f"Clicks: {click_count[0]}"

        click_btn.on_click = _on_click
        inner.add_child(click_btn)

        close_btn = Button()
        close_btn.text = "Close Window"
        close_btn.preferred_width = px(150)
        close_btn.preferred_height = px(32)
        close_btn.on_click = lambda: window_ui.close_window()
        inner.add_child(close_btn)

        panel.add_child(inner)
        window_ui.root = panel

    btn_widget.on_click = _open_widget_window
    stack.add_child(btn_widget)

    # --- Button: open a Dialog in a window ---
    btn_dialog = Button()
    btn_dialog.text = "Open Dialog in Window"
    btn_dialog.preferred_width = px(250)
    btn_dialog.preferred_height = px(36)

    status_lbl = Label()
    status_lbl.text = ""
    status_lbl.text_color = (0.5, 0.9, 0.5, 1.0)

    def _open_dialog_window():
        window_ui = ui.create_window("Settings", 450, 350)
        if window_ui is None:
            return

        # Build dialog content
        content = VStack()
        content.spacing = 12
        content.preferred_height = px(200)

        name_row = HStack()
        name_row.spacing = 8
        name_lbl = Label()
        name_lbl.text = "Name:"
        name_lbl.text_color = (0.8, 0.8, 0.8, 1.0)
        name_row.add_child(name_lbl)
        name_input = TextInput()
        name_input.text = "Player 1"
        name_input.stretch = True
        name_row.add_child(name_input)
        content.add_child(name_row)

        speed_row = HStack()
        speed_row.spacing = 8
        speed_lbl = Label()
        speed_lbl.text = "Speed:"
        speed_lbl.text_color = (0.8, 0.8, 0.8, 1.0)
        speed_row.add_child(speed_lbl)
        speed_spin = SpinBox()
        speed_spin.value = 1.0
        speed_spin.min_value = 0.1
        speed_spin.max_value = 10.0
        speed_spin.step = 0.1
        speed_spin.decimals = 1
        speed_spin.stretch = True
        speed_row.add_child(speed_spin)
        content.add_child(speed_row)

        dlg = Dialog()
        dlg.title = "Settings"
        dlg.content = content
        dlg.buttons = ["OK", "Cancel"]
        dlg.default_button = "OK"
        dlg.cancel_button = "Cancel"

        def _on_result(btn):
            if btn == "OK":
                status_lbl.text = (
                    f"Saved: name={name_input.text}, speed={speed_spin.value}"
                )
            else:
                status_lbl.text = "Cancelled"

        dlg.on_result = _on_result
        dlg.show(window_ui)

    btn_dialog.on_click = _open_dialog_window
    stack.add_child(btn_dialog)
    stack.add_child(status_lbl)

    root.add_child(stack)
    ui.root = root
    return ui


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
        raise RuntimeError(f"SDL_Init failed: {sdl2.SDL_GetError()}")

    video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_MAJOR_VERSION, 3)
    video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_MINOR_VERSION, 3)
    video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_PROFILE_MASK,
                              video.SDL_GL_CONTEXT_PROFILE_CORE)
    video.SDL_GL_SetAttribute(video.SDL_GL_DOUBLEBUFFER, 1)
    video.SDL_GL_SetAttribute(video.SDL_GL_DEPTH_SIZE, 24)

    window, gl_ctx = _create_sdl_window("tcgui Multi-Window", 600, 400)

    graphics = OpenGLGraphicsBackend.get_instance()
    graphics.ensure_ready()

    wm = _WindowManager(graphics)

    ui = build_main_ui(graphics, wm)
    wm.register_main(window, gl_ctx, ui)

    sdl2.SDL_StartTextInput()

    running = True
    while running:
        event = sdl2.SDL_Event()
        if sdl2.SDL_WaitEventTimeout(ctypes.byref(event), 16):
            # Put event back so dispatch_events can poll it
            sdl2.SDL_PushEvent(ctypes.byref(event))

        if not dispatch_events(wm):
            running = False
            break

        wm.render_all()

    wm.destroy_all()
    sdl2.SDL_Quit()


if __name__ == "__main__":
    main()
