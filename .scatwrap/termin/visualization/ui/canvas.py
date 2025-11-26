<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/ui/canvas.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from __future__ import annotations<br>
<br>
from typing import List, Tuple<br>
<br>
import numpy as np<br>
<br>
from ..backends.base import GraphicsBackend<br>
<br>
<br>
class Canvas:<br>
&#9;&quot;&quot;&quot;2D overlay composed of UI elements rendered in viewport space.&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self):<br>
&#9;&#9;self.elements: List[&quot;UIElement&quot;] = []<br>
&#9;&#9;self.active_element = None  # захват мыши<br>
<br>
&#9;def add(self, element: &quot;UIElement&quot;) -&gt; &quot;UIElement&quot;:<br>
&#9;&#9;self.elements.append(element)<br>
&#9;&#9;return element<br>
<br>
&#9;def remove(self, element: &quot;UIElement&quot;):<br>
&#9;&#9;if element in self.elements:<br>
&#9;&#9;&#9;self.elements.remove(element)<br>
<br>
&#9;def clear(self):<br>
&#9;&#9;self.elements.clear()<br>
<br>
&#9;def render(self, graphics: GraphicsBackend, context_key: int, viewport_rect: Tuple[int, int, int, int]):<br>
&#9;&#9;if not self.elements:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;graphics.set_cull_face(False)<br>
&#9;&#9;graphics.set_depth_test(False)<br>
&#9;&#9;graphics.set_blend(True)<br>
&#9;&#9;graphics.set_blend_func(&quot;src_alpha&quot;, &quot;one_minus_src_alpha&quot;)<br>
&#9;&#9;for element in self.elements:<br>
&#9;&#9;&#9;element.draw(self, graphics, context_key, viewport_rect)<br>
&#9;&#9;graphics.set_cull_face(True)<br>
&#9;&#9;graphics.set_blend(False)<br>
&#9;&#9;graphics.set_depth_test(True)<br>
<br>
&#9;def draw_vertices(self, graphics: GraphicsBackend, context_key: int, vertices):<br>
&#9;&#9;graphics.draw_ui_vertices(context_key, vertices)<br>
<br>
&#9;def draw_textured_quad(self, graphics: GraphicsBackend, context_key: int, vertices: np.ndarray):<br>
&#9;&#9;graphics.draw_ui_textured_quad(context_key, vertices)<br>
<br>
&#9;def hit_test(self, x: float, y: float, viewport_rect_pixels: Tuple[int, int, int, int]) -&gt; &quot;UIElement | None&quot;:<br>
&#9;&#9;px, py, pw, ph = viewport_rect_pixels<br>
<br>
&#9;&#9;# координаты UIElement в нормализованном 0..1 пространстве<br>
&#9;&#9;nx = (x - px) / pw<br>
&#9;&#9;ny = (y - py) / ph<br>
<br>
&#9;&#9;# проходим с конца (верхние слои имеют приоритет)<br>
&#9;&#9;for elem in reversed(self.elements):<br>
&#9;&#9;&#9;if hasattr(elem, &quot;contains&quot;):<br>
&#9;&#9;&#9;&#9;if elem.contains(nx, ny):<br>
&#9;&#9;&#9;&#9;&#9;return elem<br>
&#9;&#9;return None<br>
<br>
&#9;def mouse_down(self, x, y, viewport_rect):<br>
&#9;&#9;print(&quot;Canvas mouse down at:&quot;, (x, y))<br>
&#9;&#9;hit = self.hit_test(x, y, viewport_rect)<br>
&#9;&#9;if hit:<br>
&#9;&#9;&#9;self.active_element = hit<br>
&#9;&#9;&#9;hit.on_mouse_down(x, y)<br>
&#9;&#9;&#9;return True<br>
&#9;&#9;return False<br>
&#9;<br>
<br>
&#9;def mouse_move(self, x, y, viewport_rect):<br>
&#9;&#9;if self.active_element:<br>
&#9;&#9;&#9;self.active_element.on_mouse_move(x, y, viewport_rect)<br>
&#9;&#9;&#9;return True<br>
&#9;&#9;return False<br>
<br>
&#9;def mouse_up(self, x, y, viewport_rect):<br>
&#9;&#9;print(&quot;Canvas mouse up at:&quot;, (x, y))<br>
&#9;&#9;if self.active_element:<br>
&#9;&#9;&#9;self.active_element.on_mouse_up(x, y, viewport_rect)<br>
&#9;&#9;&#9;self.active_element = None<br>
&#9;&#9;&#9;return True<br>
&#9;&#9;return False<br>
<!-- END SCAT CODE -->
</body>
</html>
