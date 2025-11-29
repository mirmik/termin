"""Visualization world orchestrating scenes, windows and main loop."""

from __future__ import annotations

import time
from typing import List

from termin.visualization.render.renderer import Renderer
from termin.visualization.core.scene import Scene
from termin.visualization.platform.window import Window
from termin.visualization.platform.backends.glfw import GLFWWindowBackend
from termin.visualization.render.opengl.backends import OpenGLGraphicsBackend
from termin.visualization.platform.backends.base import GraphicsBackend, WindowBackend
from termin.visualization.platform.backends import (
    get_default_graphics_backend,
    get_default_window_backend,
    set_default_graphics_backend,
    set_default_window_backend,
)

# For testing purposes, set this to True to close the world after the first frame.
CLOSE_AFTER_FIRST_FRAME = False

class VisualizationWorld:
    """High-level application controller."""

    def __init__(self, graphics_backend: GraphicsBackend | None = None, window_backend: WindowBackend | None = None):
        self.graphics = graphics_backend or get_default_graphics_backend() or OpenGLGraphicsBackend()
        self.window_backend = window_backend or get_default_window_backend() or GLFWWindowBackend()
        set_default_graphics_backend(self.graphics)
        set_default_window_backend(self.window_backend)
        self.renderer = Renderer(self.graphics)
        self.scenes: List[Scene] = []
        self.windows: List[Window] = []
        self._running = False
        
        self.fps = 0

    def add_scene(self, scene: Scene) -> Scene:
        self.scenes.append(scene)
        return scene

    def remove_scene(self, scene: Scene):
        if scene in self.scenes:
            self.scenes.remove(scene)

    def create_window(self, width: int = 1280, height: int = 720, title: str = "termin viewer", **backend_kwargs) -> Window:
        share = self.windows[0] if self.windows else None
        window = Window(width=width, height=height, title=title, renderer=self.renderer, graphics=self.graphics, window_backend=self.window_backend, share=share, **backend_kwargs)
        self.windows.append(window)
        return window

    def add_window(self, window: Window):
        self.windows.append(window)

    def update_fps(self, dt):
        if dt > 0:
            self.fps = int(1.0 / dt)
        else:
            self.fps = 0

    def run(self):
        if self._running:
            return
        self._running = True
        last = time.perf_counter()

        while self.windows:
            now = time.perf_counter()
            dt = now - last
            last = now

            for scene in list(self.scenes):
                scene.update(dt)

            alive = []
            for window in list(self.windows):
                if window.should_close:
                    window.close()
                    continue
                window.update(dt)
                if window.handle.drives_render():
                    window.handle.widget.update()
                if not window.handle.drives_render():
                    window.render()
                alive.append(window)
            self.windows = alive
            self.window_backend.poll_events()
            self.update_fps(dt)

            if CLOSE_AFTER_FIRST_FRAME:
                break
            
        for window in self.windows:
            window.close()
        self.window_backend.terminate()
        self._running = False
