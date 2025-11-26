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
    &quot;&quot;&quot;2D overlay composed of UI elements rendered in viewport space.&quot;&quot;&quot;<br>
<br>
    def __init__(self):<br>
        self.elements: List[&quot;UIElement&quot;] = []<br>
        self.active_element = None  # захват мыши<br>
<br>
    def add(self, element: &quot;UIElement&quot;) -&gt; &quot;UIElement&quot;:<br>
        self.elements.append(element)<br>
        return element<br>
<br>
    def remove(self, element: &quot;UIElement&quot;):<br>
        if element in self.elements:<br>
            self.elements.remove(element)<br>
<br>
    def clear(self):<br>
        self.elements.clear()<br>
<br>
    def render(self, graphics: GraphicsBackend, context_key: int, viewport_rect: Tuple[int, int, int, int]):<br>
        if not self.elements:<br>
            return<br>
        graphics.set_cull_face(False)<br>
        graphics.set_depth_test(False)<br>
        graphics.set_blend(True)<br>
        graphics.set_blend_func(&quot;src_alpha&quot;, &quot;one_minus_src_alpha&quot;)<br>
        for element in self.elements:<br>
            element.draw(self, graphics, context_key, viewport_rect)<br>
        graphics.set_cull_face(True)<br>
        graphics.set_blend(False)<br>
        graphics.set_depth_test(True)<br>
<br>
    def draw_vertices(self, graphics: GraphicsBackend, context_key: int, vertices):<br>
        graphics.draw_ui_vertices(context_key, vertices)<br>
<br>
    def draw_textured_quad(self, graphics: GraphicsBackend, context_key: int, vertices: np.ndarray):<br>
        graphics.draw_ui_textured_quad(context_key, vertices)<br>
<br>
    def hit_test(self, x: float, y: float, viewport_rect_pixels: Tuple[int, int, int, int]) -&gt; &quot;UIElement | None&quot;:<br>
        px, py, pw, ph = viewport_rect_pixels<br>
<br>
        # координаты UIElement в нормализованном 0..1 пространстве<br>
        nx = (x - px) / pw<br>
        ny = (y - py) / ph<br>
<br>
        # проходим с конца (верхние слои имеют приоритет)<br>
        for elem in reversed(self.elements):<br>
            if hasattr(elem, &quot;contains&quot;):<br>
                if elem.contains(nx, ny):<br>
                    return elem<br>
        return None<br>
<br>
    def mouse_down(self, x, y, viewport_rect):<br>
        print(&quot;Canvas mouse down at:&quot;, (x, y))<br>
        hit = self.hit_test(x, y, viewport_rect)<br>
        if hit:<br>
            self.active_element = hit<br>
            hit.on_mouse_down(x, y)<br>
            return True<br>
        return False<br>
    <br>
<br>
    def mouse_move(self, x, y, viewport_rect):<br>
        if self.active_element:<br>
            self.active_element.on_mouse_move(x, y, viewport_rect)<br>
            return True<br>
        return False<br>
<br>
    def mouse_up(self, x, y, viewport_rect):<br>
        print(&quot;Canvas mouse up at:&quot;, (x, y))<br>
        if self.active_element:<br>
            self.active_element.on_mouse_up(x, y, viewport_rect)<br>
            self.active_element = None<br>
            return True<br>
        return False<br>
<!-- END SCAT CODE -->
</body>
</html>
