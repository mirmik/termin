from __future__ import annotations

from typing import List, Tuple

import numpy as np

from termin.visualization.platform.backends.base import GraphicsBackend


class Canvas:
    """2D overlay composed of UI elements rendered in viewport space."""

    def __init__(self):
        self.elements: List["UIElement"] = []
        self.active_element = None  # захват мыши

    def add(self, element: "UIElement") -> "UIElement":
        self.elements.append(element)
        return element

    def remove(self, element: "UIElement"):
        if element in self.elements:
            self.elements.remove(element)

    def clear(self):
        self.elements.clear()

    def render(self, graphics: GraphicsBackend, context_key: int, viewport_rect: Tuple[int, int, int, int]):
        if not self.elements:
            return
        graphics.set_cull_face(False)
        graphics.set_depth_test(False)
        graphics.set_blend(True)
        graphics.set_blend_func("src_alpha", "one_minus_src_alpha")
        for element in self.elements:
            element.draw(self, graphics, context_key, viewport_rect)
        graphics.set_cull_face(True)
        graphics.set_blend(False)
        graphics.set_depth_test(True)

    def draw_vertices(self, graphics: GraphicsBackend, context_key: int, vertices):
        graphics.draw_ui_vertices(context_key, vertices)

    def draw_textured_quad(self, graphics: GraphicsBackend, context_key: int, vertices: np.ndarray):
        graphics.draw_ui_textured_quad(context_key, vertices)

    def hit_test(self, x: float, y: float, viewport_rect_pixels: Tuple[int, int, int, int]) -> "UIElement | None":
        px, py, pw, ph = viewport_rect_pixels

        # координаты UIElement в нормализованном 0..1 пространстве
        nx = (x - px) / pw
        ny = (y - py) / ph

        # проходим с конца (верхние слои имеют приоритет)
        for elem in reversed(self.elements):
            if elem.contains(nx, ny):
                return elem
        return None

    def mouse_down(self, x, y, viewport_rect):
        hit = self.hit_test(x, y, viewport_rect)
        if hit:
            self.active_element = hit
            hit.on_mouse_down(x, y)
            return True
        return False
    

    def mouse_move(self, x, y, viewport_rect):
        if self.active_element:
            self.active_element.on_mouse_move(x, y, viewport_rect)
            return True
        return False

    def mouse_up(self, x, y, viewport_rect):
        if self.active_element:
            self.active_element.on_mouse_up(x, y, viewport_rect)
            self.active_element = None
            return True
        return False
