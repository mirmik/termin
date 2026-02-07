"""Standalone test: SDL window + OpenGL + UIRenderer widget rendering."""

from __future__ import annotations

import ctypes
import time

import sdl2
from sdl2 import video

from termin.graphics import OpenGLGraphicsBackend
from termin.visualization.platform.backends import set_default_graphics_backend
from termin.visualization.ui.widgets.ui import UI
from termin.visualization.ui.widgets.basic import Label, Button
from termin.visualization.ui.widgets.containers import VStack, Panel


def _create_sdl_window(
    title: str, width: int, height: int
) -> tuple:
    """Create SDL window with OpenGL 3.3 core context. Returns (window, gl_context)."""
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
        width,
        height,
        flags,
    )
    if not window:
        raise RuntimeError(f"SDL_CreateWindow failed: {sdl2.SDL_GetError()}")

    gl_context = video.SDL_GL_CreateContext(window)
    if not gl_context:
        video.SDL_DestroyWindow(window)
        raise RuntimeError(f"SDL_GL_CreateContext failed: {sdl2.SDL_GetError()}")

    video.SDL_GL_MakeCurrent(window, gl_context)
    video.SDL_GL_SetSwapInterval(1)  # vsync

    return window, gl_context


def _build_ui(graphics: OpenGLGraphicsBackend) -> UI:
    """Build a simple test widget tree."""
    ui = UI(graphics)

    panel = Panel()
    panel.background_color = (0.14, 0.14, 0.18, 0.95)
    panel.padding = 40
    panel.anchor = "center"
    panel.border_radius = 12

    stack = VStack()
    stack.spacing = 15
    stack.alignment = "center"

    title = Label()
    title.text = "Termin Engine"
    title.font_size = 36
    title.color = (1.0, 1.0, 1.0, 1.0)

    subtitle = Label()
    subtitle.text = "UIRenderer test — it works!"
    subtitle.font_size = 18
    subtitle.color = (0.6, 0.65, 0.75, 1.0)

    btn = Button()
    btn.text = "Click me"
    btn.on_click = lambda: print("[test_ui] Button clicked!")

    stack.add_child(title)
    stack.add_child(subtitle)
    stack.add_child(btn)
    panel.add_child(stack)

    ui.root = panel
    return ui


def _get_drawable_size(window) -> tuple[int, int]:
    w = ctypes.c_int()
    h = ctypes.c_int()
    video.SDL_GL_GetDrawableSize(window, ctypes.byref(w), ctypes.byref(h))
    return w.value, h.value


def run():
    """Entry point: create window, build UI, run event loop."""
    window, gl_context = _create_sdl_window("Termin Launcher Test", 1024, 640)

    # Initialize graphics backend (GLAD)
    graphics = OpenGLGraphicsBackend.get_instance()
    graphics.ensure_ready()
    set_default_graphics_backend(graphics)

    ui = _build_ui(graphics)

    event = sdl2.SDL_Event()
    running = True

    while running:
        # Poll events
        while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
            etype = event.type

            if etype == sdl2.SDL_QUIT:
                running = False
            elif etype == sdl2.SDL_WINDOWEVENT:
                if event.window.event == video.SDL_WINDOWEVENT_CLOSE:
                    running = False
            elif etype == sdl2.SDL_MOUSEMOTION:
                ui.mouse_move(float(event.motion.x), float(event.motion.y))
            elif etype == sdl2.SDL_MOUSEBUTTONDOWN:
                ui.mouse_down(float(event.button.x), float(event.button.y))
            elif etype == sdl2.SDL_MOUSEBUTTONUP:
                ui.mouse_up(float(event.button.x), float(event.button.y))

        # Render
        vw, vh = _get_drawable_size(window)
        graphics.bind_framebuffer(None)
        graphics.set_viewport(0, 0, vw, vh)
        graphics.clear_color_depth(0.08, 0.08, 0.10, 1.0)

        ui.render(vw, vh)

        video.SDL_GL_SwapWindow(window)

    # Cleanup
    video.SDL_GL_DeleteContext(gl_context)
    video.SDL_DestroyWindow(window)
    sdl2.SDL_Quit()


if __name__ == "__main__":
    run()
