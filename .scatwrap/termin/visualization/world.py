<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/world.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Visualization world orchestrating scenes, windows and main loop.&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
import time<br>
from typing import List, Optional<br>
<br>
from .renderer import Renderer<br>
from .scene import Scene<br>
from .window import Window<br>
from .backends.glfw import GLFWWindowBackend<br>
from .backends.opengl import OpenGLGraphicsBackend<br>
from .backends.base import GraphicsBackend, WindowBackend<br>
from .backends import set_default_graphics_backend, set_default_window_backend, get_default_graphics_backend, get_default_window_backend<br>
<br>
# For testing purposes, set this to True to close the world after the first frame.<br>
CLOSE_AFTER_FIRST_FRAME = False<br>
<br>
class VisualizationWorld:<br>
    &quot;&quot;&quot;High-level application controller.&quot;&quot;&quot;<br>
<br>
    def __init__(self, graphics_backend: GraphicsBackend | None = None, window_backend: WindowBackend | None = None):<br>
        self.graphics = graphics_backend or get_default_graphics_backend() or OpenGLGraphicsBackend()<br>
        self.window_backend = window_backend or get_default_window_backend() or GLFWWindowBackend()<br>
        set_default_graphics_backend(self.graphics)<br>
        set_default_window_backend(self.window_backend)<br>
        self.renderer = Renderer(self.graphics)<br>
        self.scenes: List[Scene] = []<br>
        self.windows: List[Window] = []<br>
        self._running = False<br>
        <br>
        self.fps = 0<br>
<br>
    def add_scene(self, scene: Scene) -&gt; Scene:<br>
        self.scenes.append(scene)<br>
        return scene<br>
<br>
    def remove_scene(self, scene: Scene):<br>
        if scene in self.scenes:<br>
            self.scenes.remove(scene)<br>
<br>
    def create_window(self, width: int = 1280, height: int = 720, title: str = &quot;termin viewer&quot;, **backend_kwargs) -&gt; Window:<br>
        share = self.windows[0] if self.windows else None<br>
        window = Window(width=width, height=height, title=title, renderer=self.renderer, graphics=self.graphics, window_backend=self.window_backend, share=share, **backend_kwargs)<br>
        self.windows.append(window)<br>
        return window<br>
<br>
    def add_window(self, window: Window):<br>
        self.windows.append(window)<br>
<br>
    def update_fps(self, dt):<br>
        if dt &gt; 0:<br>
            self.fps = int(1.0 / dt)<br>
        else:<br>
            self.fps = 0<br>
<br>
    def run(self):<br>
        if self._running:<br>
            return<br>
        self._running = True<br>
        last = time.perf_counter()<br>
<br>
        while self.windows:<br>
            now = time.perf_counter()<br>
            dt = now - last<br>
            last = now<br>
<br>
            for scene in list(self.scenes):<br>
                scene.update(dt)<br>
<br>
            alive = []<br>
            for window in list(self.windows):<br>
                if window.should_close:<br>
                    window.close()<br>
                    continue<br>
                window.update(dt)<br>
                if window.handle.drives_render():<br>
                    window.handle.widget.update()<br>
                if not window.handle.drives_render():<br>
                    window.render()<br>
                alive.append(window)<br>
            self.windows = alive<br>
            self.window_backend.poll_events()<br>
            self.update_fps(dt)<br>
<br>
            if CLOSE_AFTER_FIRST_FRAME:<br>
                break<br>
            <br>
        for window in self.windows:<br>
            window.close()<br>
        self.window_backend.terminate()<br>
        self._running = False<br>
<!-- END SCAT CODE -->
</body>
</html>
