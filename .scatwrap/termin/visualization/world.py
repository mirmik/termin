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
&#9;&quot;&quot;&quot;High-level application controller.&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, graphics_backend: GraphicsBackend | None = None, window_backend: WindowBackend | None = None):<br>
&#9;&#9;self.graphics = graphics_backend or get_default_graphics_backend() or OpenGLGraphicsBackend()<br>
&#9;&#9;self.window_backend = window_backend or get_default_window_backend() or GLFWWindowBackend()<br>
&#9;&#9;set_default_graphics_backend(self.graphics)<br>
&#9;&#9;set_default_window_backend(self.window_backend)<br>
&#9;&#9;self.renderer = Renderer(self.graphics)<br>
&#9;&#9;self.scenes: List[Scene] = []<br>
&#9;&#9;self.windows: List[Window] = []<br>
&#9;&#9;self._running = False<br>
&#9;&#9;<br>
&#9;&#9;self.fps = 0<br>
<br>
&#9;def add_scene(self, scene: Scene) -&gt; Scene:<br>
&#9;&#9;self.scenes.append(scene)<br>
&#9;&#9;return scene<br>
<br>
&#9;def remove_scene(self, scene: Scene):<br>
&#9;&#9;if scene in self.scenes:<br>
&#9;&#9;&#9;self.scenes.remove(scene)<br>
<br>
&#9;def create_window(self, width: int = 1280, height: int = 720, title: str = &quot;termin viewer&quot;, **backend_kwargs) -&gt; Window:<br>
&#9;&#9;share = self.windows[0] if self.windows else None<br>
&#9;&#9;window = Window(width=width, height=height, title=title, renderer=self.renderer, graphics=self.graphics, window_backend=self.window_backend, share=share, **backend_kwargs)<br>
&#9;&#9;self.windows.append(window)<br>
&#9;&#9;return window<br>
<br>
&#9;def add_window(self, window: Window):<br>
&#9;&#9;self.windows.append(window)<br>
<br>
&#9;def update_fps(self, dt):<br>
&#9;&#9;if dt &gt; 0:<br>
&#9;&#9;&#9;self.fps = int(1.0 / dt)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;self.fps = 0<br>
<br>
&#9;def run(self):<br>
&#9;&#9;if self._running:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;self._running = True<br>
&#9;&#9;last = time.perf_counter()<br>
<br>
&#9;&#9;while self.windows:<br>
&#9;&#9;&#9;now = time.perf_counter()<br>
&#9;&#9;&#9;dt = now - last<br>
&#9;&#9;&#9;last = now<br>
<br>
&#9;&#9;&#9;for scene in list(self.scenes):<br>
&#9;&#9;&#9;&#9;scene.update(dt)<br>
<br>
&#9;&#9;&#9;alive = []<br>
&#9;&#9;&#9;for window in list(self.windows):<br>
&#9;&#9;&#9;&#9;if window.should_close:<br>
&#9;&#9;&#9;&#9;&#9;window.close()<br>
&#9;&#9;&#9;&#9;&#9;continue<br>
&#9;&#9;&#9;&#9;window.update(dt)<br>
&#9;&#9;&#9;&#9;if window.handle.drives_render():<br>
&#9;&#9;&#9;&#9;&#9;window.handle.widget.update()<br>
&#9;&#9;&#9;&#9;if not window.handle.drives_render():<br>
&#9;&#9;&#9;&#9;&#9;window.render()<br>
&#9;&#9;&#9;&#9;alive.append(window)<br>
&#9;&#9;&#9;self.windows = alive<br>
&#9;&#9;&#9;self.window_backend.poll_events()<br>
&#9;&#9;&#9;self.update_fps(dt)<br>
<br>
&#9;&#9;&#9;if CLOSE_AFTER_FIRST_FRAME:<br>
&#9;&#9;&#9;&#9;break<br>
&#9;&#9;&#9;<br>
&#9;&#9;for window in self.windows:<br>
&#9;&#9;&#9;window.close()<br>
&#9;&#9;self.window_backend.terminate()<br>
&#9;&#9;self._running = False<br>
<!-- END SCAT CODE -->
</body>
</html>
