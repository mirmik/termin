"""Canvas demo — zoomable image viewer with selection rectangle.

Demonstrates: Canvas widget, pan/zoom, overlay drawing, coordinate transforms.

Requirements: tcbase, tgfx, tcgui, PySDL2, Pillow (or numpy-only fallback)
Run: python3 examples/sdl_canvas_demo.py
"""

import ctypes
import sdl2
from sdl2 import video
import numpy as np

from tgfx import OpenGLGraphicsBackend
from tcbase import Key, MouseButton, Mods

from tcgui.widgets.ui import UI
from tcgui.widgets.canvas import Canvas
from tcgui.widgets.label import Label
from tcgui.widgets.button import Button
from tcgui.widgets.hstack import HStack
from tcgui.widgets.vstack import VStack
from tcgui.widgets.panel import Panel
from tcgui.widgets.status_bar import StatusBar
from tcgui.widgets.units import px, pct


# --- SDL helpers (same as showcase) ---

def create_window(title: str, width: int, height: int):
    if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
        raise RuntimeError(f"SDL_Init failed: {sdl2.SDL_GetError()}")
    video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_MAJOR_VERSION, 3)
    video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_MINOR_VERSION, 3)
    video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_PROFILE_MASK,
                              video.SDL_GL_CONTEXT_PROFILE_CORE)
    video.SDL_GL_SetAttribute(video.SDL_GL_DOUBLEBUFFER, 1)
    video.SDL_GL_SetAttribute(video.SDL_GL_DEPTH_SIZE, 24)
    flags = (video.SDL_WINDOW_OPENGL | video.SDL_WINDOW_RESIZABLE |
             video.SDL_WINDOW_SHOWN)
    window = video.SDL_CreateWindow(title.encode("utf-8"),
                                    video.SDL_WINDOWPOS_CENTERED,
                                    video.SDL_WINDOWPOS_CENTERED,
                                    width, height, flags)
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


def translate_key(scancode):
    if scancode in _KEY_MAP:
        return _KEY_MAP[scancode]
    keycode = sdl2.SDL_GetKeyFromScancode(scancode)
    if 0 <= keycode < 128:
        try:
            return Key(keycode)
        except ValueError:
            pass
    return Key.UNKNOWN


def translate_mods(sdl_mods):
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


def translate_button(sdl_button):
    return _SDL_BUTTON_MAP.get(sdl_button, MouseButton.LEFT)


# --- Generate test image ---

def make_test_image(width=512, height=512):
    """Generate a colorful test image as (H, W, 4) uint8 RGBA."""
    img = np.zeros((height, width, 4), dtype=np.uint8)
    img[:, :, 3] = 255  # opaque

    # Gradient background
    for y in range(height):
        for x in range(width):
            img[y, x, 0] = int(255 * x / width)
            img[y, x, 1] = int(255 * y / height)
            img[y, x, 2] = 128

    # Checkerboard overlay
    tile = 32
    for y in range(height):
        for x in range(width):
            if ((x // tile) + (y // tile)) % 2 == 0:
                img[y, x, :3] = np.clip(img[y, x, :3].astype(int) + 30, 0, 255).astype(np.uint8)

    # Center circle
    cy, cx = height // 2, width // 2
    radius = min(width, height) // 4
    yy, xx = np.ogrid[:height, :width]
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    mask = dist < radius
    img[mask, 0] = 255
    img[mask, 1] = 200
    img[mask, 2] = 50

    return img


# --- UI ---

def build_ui(graphics):
    root = VStack()
    root.preferred_width = pct(100)
    root.preferred_height = pct(100)
    root.spacing = 0
    root.alignment = "left"

    # Status bar
    status_bar = StatusBar()
    status_bar.set_text("Canvas Demo | Middle-drag: pan | Scroll: zoom")

    # Toolbar
    toolbar = HStack()
    toolbar.preferred_width = pct(100)
    toolbar.preferred_height = px(36)
    toolbar.spacing = 8
    toolbar.alignment = "center"
    toolbar_bg = Panel()
    toolbar_bg.preferred_width = pct(100)
    toolbar_bg.preferred_height = px(36)
    toolbar_bg.background_color = (0.2, 0.2, 0.2, 1.0)
    toolbar_bg.padding = 6

    # Selection state
    sel_state = {"active": False, "start": None, "end": None, "rect": None}

    # Canvas
    canvas = Canvas()
    canvas.preferred_width = pct(100)
    canvas.preferred_height = pct(100)

    img = make_test_image(512, 512)
    canvas.set_image(img)

    # Buttons
    btn_fit = Button()
    btn_fit.text = "Fit"
    btn_fit.padding = 6
    btn_fit.on_click = lambda: (canvas.fit_in_view(),
                                status_bar.show_message("Fit to view"))

    btn_100 = Button()
    btn_100.text = "100%"
    btn_100.padding = 6
    btn_100.on_click = lambda: (canvas.set_zoom(1.0),
                                status_bar.show_message("Zoom: 100%"))

    btn_sel = Button()
    btn_sel.text = "Select"
    btn_sel.padding = 6

    def toggle_select():
        sel_state["active"] = not sel_state["active"]
        sel_state["start"] = None
        sel_state["end"] = None
        sel_state["rect"] = None
        if sel_state["active"]:
            canvas.cursor = "cross"
            status_bar.show_message("Selection mode: drag to select")
        else:
            canvas.cursor = ""
            status_bar.show_message("Selection mode off")

    btn_sel.on_click = toggle_select

    zoom_label = Label()
    zoom_label.text = "Zoom: 100%"
    zoom_label.font_size = 12
    zoom_label.color = (0.7, 0.7, 0.7, 1.0)

    toolbar_row = HStack()
    toolbar_row.spacing = 8
    toolbar_row.alignment = "center"
    toolbar_row.add_child(btn_fit)
    toolbar_row.add_child(btn_100)
    toolbar_row.add_child(btn_sel)
    toolbar_row.add_child(zoom_label)
    toolbar_bg.add_child(toolbar_row)
    root.add_child(toolbar_bg)

    # Canvas callbacks
    def on_zoom(z):
        zoom_label.text = f"Zoom: {z:.0%}"

    canvas.on_zoom_changed = on_zoom

    def on_move(ix, iy):
        size = canvas.image_size
        if size:
            w, h = size
            if 0 <= ix < w and 0 <= iy < h:
                r, g, b = img[int(iy), int(ix), :3]
                status_bar.set_text(
                    f"({ix:.0f}, {iy:.0f}) | RGB({r}, {g}, {b}) | Zoom: {canvas.zoom:.0%}")
            else:
                status_bar.set_text(f"({ix:.0f}, {iy:.0f}) | outside | Zoom: {canvas.zoom:.0%}")

        # Selection drag
        if sel_state["active"] and sel_state["start"] is not None:
            sel_state["end"] = (ix, iy)

    canvas.on_canvas_mouse_move = on_move

    def on_down(ix, iy, button):
        if sel_state["active"] and button == MouseButton.LEFT:
            sel_state["start"] = (ix, iy)
            sel_state["end"] = (ix, iy)
            sel_state["rect"] = None

    canvas.on_canvas_mouse_down = on_down

    def on_up(ix, iy):
        if sel_state["active"] and sel_state["start"] is not None:
            sx, sy = sel_state["start"]
            x0, y0 = min(sx, ix), min(sy, iy)
            x1, y1 = max(sx, ix), max(sy, iy)
            if x1 - x0 > 2 and y1 - y0 > 2:
                sel_state["rect"] = (x0, y0, x1, y1)
                status_bar.show_message(
                    f"Selected: ({x0:.0f},{y0:.0f})-({x1:.0f},{y1:.0f}) "
                    f"[{x1-x0:.0f}x{y1-y0:.0f}]")
            sel_state["start"] = None
            sel_state["end"] = None

    canvas.on_canvas_mouse_up = on_up

    def draw_overlay(c, renderer):
        # Draw in-progress selection
        rect = None
        if sel_state["start"] is not None and sel_state["end"] is not None:
            sx, sy = sel_state["start"]
            ex, ey = sel_state["end"]
            rect = (min(sx, ex), min(sy, ey), max(sx, ex), max(sy, ey))
        elif sel_state["rect"] is not None:
            rect = sel_state["rect"]

        if rect:
            x0, y0, x1, y1 = rect
            wx0, wy0 = c.image_to_widget(x0, y0)
            wx1, wy1 = c.image_to_widget(x1, y1)
            w = wx1 - wx0
            h = wy1 - wy0
            # Fill
            renderer.draw_rect(wx0, wy0, w, h, (0.2, 0.5, 0.9, 0.15))
            # Outline
            renderer.draw_rect_outline(wx0, wy0, w, h,
                                       (0.3, 0.6, 1.0, 0.8), thickness=2)

    canvas.on_render_overlay = draw_overlay

    root.add_child(canvas)
    root.add_child(status_bar)

    ui = UI(graphics)
    ui.root = root
    return ui, canvas


# --- Main ---

def main():
    window, gl_ctx = create_window("tcgui — Canvas Demo", 800, 600)
    graphics = OpenGLGraphicsBackend.get_instance()
    graphics.ensure_ready()

    ui, canvas = build_ui(graphics)

    # Cursor support
    _SDL_CURSORS = {
        "": sdl2.SDL_SYSTEM_CURSOR_ARROW,
        "arrow": sdl2.SDL_SYSTEM_CURSOR_ARROW,
        "cross": sdl2.SDL_SYSTEM_CURSOR_CROSSHAIR,
        "hand": sdl2.SDL_SYSTEM_CURSOR_HAND,
        "text": sdl2.SDL_SYSTEM_CURSOR_IBEAM,
        "move": sdl2.SDL_SYSTEM_CURSOR_SIZEALL,
    }
    _cursor_cache = {}

    def set_cursor(name):
        cursor_id = _SDL_CURSORS.get(name, sdl2.SDL_SYSTEM_CURSOR_ARROW)
        if cursor_id not in _cursor_cache:
            _cursor_cache[cursor_id] = sdl2.SDL_CreateSystemCursor(cursor_id)
        sdl2.SDL_SetCursor(_cursor_cache[cursor_id])

    ui.on_cursor_changed = set_cursor

    sdl2.SDL_StartTextInput()
    event = sdl2.SDL_Event()
    running = True
    first_frame = True

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
            ui.mouse_down(float(ev.button.x), float(ev.button.y),
                          translate_button(ev.button.button))
        elif t == sdl2.SDL_MOUSEBUTTONUP:
            ui.mouse_up(float(ev.button.x), float(ev.button.y))
        elif t == sdl2.SDL_MOUSEWHEEL:
            mx, my = ctypes.c_int(), ctypes.c_int()
            sdl2.SDL_GetMouseState(ctypes.byref(mx), ctypes.byref(my))
            ui.mouse_wheel(float(ev.wheel.x), float(ev.wheel.y),
                           float(mx.value), float(my.value))
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

        # Fit on first frame (canvas needs layout first)
        if first_frame:
            canvas.fit_in_view()
            first_frame = False

        video.SDL_GL_SwapWindow(window)

    video.SDL_GL_DeleteContext(gl_ctx)
    video.SDL_DestroyWindow(window)
    sdl2.SDL_Quit()


if __name__ == "__main__":
    main()
