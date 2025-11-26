<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/ui/elements.py</title>
</head>
<body>
<pre><code>
from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple
import numpy as np
from ..material import Material

IDENTITY = np.identity(4, dtype=np.float32)



class UIElement:
    &quot;&quot;&quot;Base UI element rendered inside a canvas.&quot;&quot;&quot;

    material: Material | None = None

    def draw(self, canvas, graphics, context_key: int, viewport_rect: Tuple[int, int, int, int]):
        raise NotImplementedError

    def _require_material(self) -&gt; Material:
        if self.material is None:
            raise RuntimeError(f&quot;{self.__class__.__name__} has no material assigned.&quot;)
        return self.material
    
    def contains(self, nx: float, ny: float) -&gt; bool:
        return False
    
    def on_mouse_down(self, x: float, y: float, viewport_rect):
        pass

    def on_mouse_move(self, x: float, y: float, viewport_rect):
        pass

    def on_mouse_up(self, x: float, y: float, viewport_rect):
        pass  


@dataclass
class UIRectangle(UIElement):
    &quot;&quot;&quot;Axis-aligned rectangle defined in normalized viewport coordinates.&quot;&quot;&quot;

    position: Tuple[float, float]
    size: Tuple[float, float]
    color: Tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)
    material: Material | None = None

    def _to_clip_vertices(self) -&gt; np.ndarray:
        x, y = self.position
        w, h = self.size
        left = x * 2.0 - 1.0
        right = (x + w) * 2.0 - 1.0
        top = 1.0 - y * 2.0
        bottom = 1.0 - (y + h) * 2.0
        return np.array(
            [
                [left, top],
                [right, top],
                [left, bottom],
                [right, bottom],
            ],
            dtype=np.float32,
        )

    def contains(self, nx: float, ny: float) -&gt; bool:
        x, y = self.position
        w, h = self.size
        return x &lt;= nx &lt;= x + w and y &lt;= ny &lt;= y + h

    def draw(self, canvas, graphics, context_key: int, viewport_rect: Tuple[int, int, int, int]):
        material = self._require_material()
        material.apply(IDENTITY, IDENTITY, IDENTITY, graphics=graphics, context_key=context_key)
        vertices = self._to_clip_vertices()
        shader = material.shader
        shader.set_uniform_vec4(&quot;u_color&quot;, np.array(self.color, dtype=np.float32))
        shader.set_uniform_int(&quot;u_use_texture&quot;, 0)
        canvas.draw_vertices(graphics, context_key, vertices)


@dataclass
class UIText(UIElement):
    text: str
    position: tuple[float, float]
    color: tuple[float, float, float, float] = (1, 1, 1, 1)
    scale: float = 1.0
    material: Material | None = None

    def draw(self, canvas, graphics, context_key, viewport):
        if not hasattr(canvas, &quot;font&quot;):
            return
        material = self._require_material()
        material.apply(IDENTITY, IDENTITY, IDENTITY, graphics=graphics, context_key=context_key)

        shader = material.shader
        shader.set_uniform_vec4(&quot;u_color&quot;, np.array(self.color, dtype=np.float32))
        shader.set_uniform_int(&quot;u_use_texture&quot;, 1)
        texture_handle = canvas.font.ensure_texture(graphics, context_key=context_key)
        texture_handle.bind(0)
        shader.set_uniform_int(&quot;u_texture&quot;, 0)

        x, y = self.position
        px, py, pw, ph = viewport

        cx = x
        cy = y

        for ch in self.text:
            if ch not in canvas.font.glyphs:
                continue
            glyph = canvas.font.glyphs[ch]
            w, h = glyph[&quot;size&quot;]
            u0, v0, u1, v1 = glyph[&quot;uv&quot;]

            sx = w * self.scale / pw * 2
            sy = h * self.scale / ph * 2

            vx0 = cx * 2 - 1
            vy0 = 1 - cy * 2
            vx1 = (cx + w * self.scale / pw) * 2 - 1
            vy1 = 1 - (cy + h * self.scale / ph) * 2

            vertices = np.array([
                [vx0, vy0, u0, v0],
                [vx1, vy0, u1, v0],
                [vx0, vy1, u0, v1],
                [vx1, vy1, u1, v1],
            ], dtype=np.float32)

            canvas.draw_textured_quad(graphics, context_key, vertices)

            cx += (w * self.scale) / pw


@dataclass
class UIButton(UIElement):
    position: tuple[float, float]
    size: tuple[float, float]
    text: str
    on_click: callable | None = None

    material: Material | None = None          # фон
    text_material: Material | None = None     # текст

    background_color: tuple = (0.2, 0.2, 0.25, 1.0)
    text_color: tuple = (1, 1, 1, 1)

    def __post_init__(self):
        if self.material is None:
            raise RuntimeError(&quot;UIButton requires material for background&quot;)
        if self.text_material is None:
            raise RuntimeError(&quot;UIButton requires text_material for label&quot;)

        self.bg = UIRectangle(
            position=self.position,
            size=self.size,
            color=self.background_color,
            material=self.material,
        )

        # небольшое смещение текста внутрь
        text_pos = (
            self.position[0] + 0.01,
            self.position[1] + 0.01,
        )

        self.label = UIText(
            text=self.text,
            position=text_pos,
            color=self.text_color,
            scale=1.0,
            material=self.text_material,
        )

    def contains(self, nx, ny):
        return self.bg.contains(nx, ny)

    def draw(self, canvas, graphics, context_key, viewport_rect):
        self.bg.draw(canvas, graphics, context_key, viewport_rect)
        self.label.draw(canvas, graphics, context_key, viewport_rect)

@dataclass
class UISlider(UIElement):
    position: tuple[float, float]              # нормализовано 0..1
    size: tuple[float, float]                  # ширина/высота трека
    value: float = 0.5                         # 0..1
    on_change: callable | None = None
    material: Material | None = None
    handle_material: Material | None = None

    _dragging: bool = False

    def _track_vertices(self):
        rect = UIRectangle(
            position=self.position,
            size=self.size,
            color=(0.3, 0.3, 0.3, 1),
            material=self.material
        )
        return rect

    def _handle_position(self):
        x, y = self.position
        w, h = self.size
        hx = x + self.value * w
        return hx, y

    def draw(self, canvas, graphics, context_key, viewport_rect):
        track = self._track_vertices()
        track.draw(canvas, graphics, context_key, viewport_rect)

        hx, hy = self._handle_position()
        handle = UIRectangle(
            position=(hx - 0.01, hy),
            size=(0.02, self.size[1]),
            color=(0.8, 0.8, 0.9, 1),
            material=self.handle_material
        )
        handle.draw(canvas, graphics, context_key, viewport_rect)

    def contains(self, nx, ny):
        x, y = self.position
        w, h = self.size
        return x &lt;= nx &lt;= x + w and y &lt;= ny &lt;= y + h

    # === Events ===
    def on_mouse_down(self, x, y):
        print(&quot;Slider mouse down at:&quot;, (x, y))
        self._dragging = True

    def on_mouse_move(self, x, y, viewport_rect):
        # преобразуем в нормализованные координаты
        px, py, pw, ph = viewport_rect
        nx = (x - px) / pw
        ny = (y - py) / ph

        print(&quot;Slider mouse move at:&quot;, (nx, ny))
        if not self._dragging:
            return
        x0, y0 = self.position
        w, h = self.size
        t = (nx - x0) / w
        t = max(0.0, min(1.0, t))
        self.value = t
        if self.on_change:
            self.on_change(self.value)


    def on_mouse_up(self, x, y, viewport_rect):
        print(&quot;Slider mouse up at:&quot;, (x, y))
        self._dragging = False

</code></pre>
</body>
</html>
