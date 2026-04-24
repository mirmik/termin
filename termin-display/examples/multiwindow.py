"""Multi-window example for termin.display.

Opens one primary BackendWindow and one (or more) secondary windows
that share the primary's IRenderDevice. Each window gets its own
colour attachment and is filled with an animated clear colour — a
minimal demonstration that independent presentation works through a
single tgfx2 device on both OpenGL and Vulkan.

Run:
    TERMIN_BACKEND=opengl python3 examples/multiwindow.py
    TERMIN_BACKEND=vulkan python3 examples/multiwindow.py

Keys:
    N   — open another secondary window
    ESC — close focused window (primary → exit)
"""

from __future__ import annotations

import ctypes
import time

import sdl2

from tgfx._tgfx_native import Tgfx2Context, Tgfx2PixelFormat

from termin.display import (
    BackendWindow,
    BackendWindowEntry,
    BackendWindowManager,
)


# ---------------------------------------------------------------------------
# Per-window state — an offscreen colour attachment sized to the window.
# Re-created on resize so present() gets a pixel-perfect source.
# ---------------------------------------------------------------------------

class WindowState:
    def __init__(self, ctx: Tgfx2Context, width: int, height: int,
                 hue_offset: float) -> None:
        self.ctx = ctx
        self.hue_offset = hue_offset
        self.width = width
        self.height = height
        self.tex = ctx.context.create_color_attachment(
            width, height, Tgfx2PixelFormat.RGBA8_UNorm)

    def ensure_size(self, width: int, height: int) -> None:
        if width == self.width and height == self.height:
            return
        if self.tex is not None:
            self.ctx.context.destroy_texture(self.tex)
        self.width = width
        self.height = height
        self.tex = self.ctx.context.create_color_attachment(
            width, height, Tgfx2PixelFormat.RGBA8_UNorm)

    def destroy(self) -> None:
        if self.tex is not None:
            self.ctx.context.destroy_texture(self.tex)
            self.tex = None


def _destroy_state(entry: BackendWindowEntry) -> None:
    if isinstance(entry.host_data, WindowState):
        entry.host_data.destroy()


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def _hsv_to_rgb(h: float, s: float, v: float) -> tuple[float, float, float]:
    i = int(h * 6.0)
    f = h * 6.0 - i
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)
    i = i % 6
    if i == 0: return v, t, p
    if i == 1: return q, v, p
    if i == 2: return p, v, t
    if i == 3: return p, q, v
    if i == 4: return t, p, v
    return v, p, q


# ---------------------------------------------------------------------------
# Render + secondary spawn
# ---------------------------------------------------------------------------

def render_entry(entry: BackendWindowEntry, ctx: Tgfx2Context, t: float) -> None:
    state: WindowState = entry.host_data
    w, h = entry.window.framebuffer_size()
    if w <= 0 or h <= 0:
        return
    state.ensure_size(w, h)

    hue = (t * 0.1 + state.hue_offset) % 1.0
    r, g, b = _hsv_to_rgb(hue, 0.6, 0.9)

    # Frame lifecycle: begin_frame builds a command list, the pass
    # records into it, end_frame submits. present() then publishes
    # the resulting texture. Don't nest present() inside the frame —
    # it does its own submits and the live cmd list would trip over
    # them.
    ctx.context.begin_frame()
    ctx.context.begin_pass(state.tex,
                            clear_color_enabled=True,
                            r=r, g=g, b=b, a=1.0)
    ctx.context.end_pass()
    ctx.context.end_frame()
    entry.window.present(state.tex)


_secondary_counter = [0]


def open_secondary(wm: BackendWindowManager, ctx: Tgfx2Context) -> None:
    _secondary_counter[0] += 1
    n = _secondary_counter[0]
    entry = wm.create_window(
        f"Secondary #{n}", 640, 480, on_destroy=_destroy_state)
    entry.host_data = WindowState(ctx, 640, 480, hue_offset=n * 0.2)


# ---------------------------------------------------------------------------
# Event pump
# ---------------------------------------------------------------------------

def pump_events(wm: BackendWindowManager, ctx: Tgfx2Context) -> bool:
    event = sdl2.SDL_Event()
    while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
        etype = event.type

        if etype == sdl2.SDL_QUIT:
            return False

        if etype == sdl2.SDL_WINDOWEVENT:
            if event.window.event == sdl2.SDL_WINDOWEVENT_CLOSE:
                if wm.handle_window_close(event.window.windowID):
                    return False
            continue

        if etype == sdl2.SDL_KEYDOWN:
            sc = event.key.keysym.scancode
            if sc == sdl2.SDL_SCANCODE_ESCAPE:
                if wm.handle_window_close(event.key.windowID):
                    return False
            elif sc == sdl2.SDL_SCANCODE_N:
                open_secondary(wm, ctx)

    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
        raise RuntimeError(f"SDL_Init failed: {sdl2.SDL_GetError()}")

    main_window = BackendWindow("termin.display multi-window (primary)", 800, 600)
    ctx = Tgfx2Context.from_window(
        main_window.device_ptr(), main_window.context_ptr())

    wm = BackendWindowManager()
    primary_entry = wm.register_main(
        main_window,
        host_data=WindowState(ctx, 800, 600, hue_offset=0.0),
        on_destroy=_destroy_state)

    # Open one secondary right away; press 'N' to pop more.
    open_secondary(wm, ctx)

    print(f"termin.display multi-window example ({ctx.backend}).")
    print("  N   — open another secondary window")
    print("  ESC — close focused window (primary → exit)")

    start = time.monotonic()
    running = True
    while running:
        t = time.monotonic() - start

        if not pump_events(wm, ctx):
            running = False
            break

        for entry in list(wm.entries):
            render_entry(entry, ctx, t)

        if primary_entry.window.should_close():
            running = False

    wm.destroy_all()
    sdl2.SDL_Quit()


if __name__ == "__main__":
    main()
