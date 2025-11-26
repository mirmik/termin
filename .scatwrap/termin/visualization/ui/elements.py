<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/ui/elements.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from __future__ import annotations<br>
from dataclasses import dataclass<br>
from typing import Tuple<br>
import numpy as np<br>
from ..material import Material<br>
<br>
IDENTITY = np.identity(4, dtype=np.float32)<br>
<br>
<br>
<br>
class UIElement:<br>
    &quot;&quot;&quot;Base UI element rendered inside a canvas.&quot;&quot;&quot;<br>
<br>
    material: Material | None = None<br>
<br>
    def draw(self, canvas, graphics, context_key: int, viewport_rect: Tuple[int, int, int, int]):<br>
        raise NotImplementedError<br>
<br>
    def _require_material(self) -&gt; Material:<br>
        if self.material is None:<br>
            raise RuntimeError(f&quot;{self.__class__.__name__} has no material assigned.&quot;)<br>
        return self.material<br>
    <br>
    def contains(self, nx: float, ny: float) -&gt; bool:<br>
        return False<br>
    <br>
    def on_mouse_down(self, x: float, y: float, viewport_rect):<br>
        pass<br>
<br>
    def on_mouse_move(self, x: float, y: float, viewport_rect):<br>
        pass<br>
<br>
    def on_mouse_up(self, x: float, y: float, viewport_rect):<br>
        pass  <br>
<br>
<br>
@dataclass<br>
class UIRectangle(UIElement):<br>
    &quot;&quot;&quot;Axis-aligned rectangle defined in normalized viewport coordinates.&quot;&quot;&quot;<br>
<br>
    position: Tuple[float, float]<br>
    size: Tuple[float, float]<br>
    color: Tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)<br>
    material: Material | None = None<br>
<br>
    def _to_clip_vertices(self) -&gt; np.ndarray:<br>
        x, y = self.position<br>
        w, h = self.size<br>
        left = x * 2.0 - 1.0<br>
        right = (x + w) * 2.0 - 1.0<br>
        top = 1.0 - y * 2.0<br>
        bottom = 1.0 - (y + h) * 2.0<br>
        return np.array(<br>
            [<br>
                [left, top],<br>
                [right, top],<br>
                [left, bottom],<br>
                [right, bottom],<br>
            ],<br>
            dtype=np.float32,<br>
        )<br>
<br>
    def contains(self, nx: float, ny: float) -&gt; bool:<br>
        x, y = self.position<br>
        w, h = self.size<br>
        return x &lt;= nx &lt;= x + w and y &lt;= ny &lt;= y + h<br>
<br>
    def draw(self, canvas, graphics, context_key: int, viewport_rect: Tuple[int, int, int, int]):<br>
        material = self._require_material()<br>
        material.apply(IDENTITY, IDENTITY, IDENTITY, graphics=graphics, context_key=context_key)<br>
        vertices = self._to_clip_vertices()<br>
        shader = material.shader<br>
        shader.set_uniform_vec4(&quot;u_color&quot;, np.array(self.color, dtype=np.float32))<br>
        shader.set_uniform_int(&quot;u_use_texture&quot;, 0)<br>
        canvas.draw_vertices(graphics, context_key, vertices)<br>
<br>
<br>
@dataclass<br>
class UIText(UIElement):<br>
    text: str<br>
    position: tuple[float, float]<br>
    color: tuple[float, float, float, float] = (1, 1, 1, 1)<br>
    scale: float = 1.0<br>
    material: Material | None = None<br>
<br>
    def draw(self, canvas, graphics, context_key, viewport):<br>
        if not hasattr(canvas, &quot;font&quot;):<br>
            return<br>
        material = self._require_material()<br>
        material.apply(IDENTITY, IDENTITY, IDENTITY, graphics=graphics, context_key=context_key)<br>
<br>
        shader = material.shader<br>
        shader.set_uniform_vec4(&quot;u_color&quot;, np.array(self.color, dtype=np.float32))<br>
        shader.set_uniform_int(&quot;u_use_texture&quot;, 1)<br>
        texture_handle = canvas.font.ensure_texture(graphics, context_key=context_key)<br>
        texture_handle.bind(0)<br>
        shader.set_uniform_int(&quot;u_texture&quot;, 0)<br>
<br>
        x, y = self.position<br>
        px, py, pw, ph = viewport<br>
<br>
        cx = x<br>
        cy = y<br>
<br>
        for ch in self.text:<br>
            if ch not in canvas.font.glyphs:<br>
                continue<br>
            glyph = canvas.font.glyphs[ch]<br>
            w, h = glyph[&quot;size&quot;]<br>
            u0, v0, u1, v1 = glyph[&quot;uv&quot;]<br>
<br>
            sx = w * self.scale / pw * 2<br>
            sy = h * self.scale / ph * 2<br>
<br>
            vx0 = cx * 2 - 1<br>
            vy0 = 1 - cy * 2<br>
            vx1 = (cx + w * self.scale / pw) * 2 - 1<br>
            vy1 = 1 - (cy + h * self.scale / ph) * 2<br>
<br>
            vertices = np.array([<br>
                [vx0, vy0, u0, v0],<br>
                [vx1, vy0, u1, v0],<br>
                [vx0, vy1, u0, v1],<br>
                [vx1, vy1, u1, v1],<br>
            ], dtype=np.float32)<br>
<br>
            canvas.draw_textured_quad(graphics, context_key, vertices)<br>
<br>
            cx += (w * self.scale) / pw<br>
<br>
<br>
@dataclass<br>
class UIButton(UIElement):<br>
    position: tuple[float, float]<br>
    size: tuple[float, float]<br>
    text: str<br>
    on_click: callable | None = None<br>
<br>
    material: Material | None = None          # фон<br>
    text_material: Material | None = None     # текст<br>
<br>
    background_color: tuple = (0.2, 0.2, 0.25, 1.0)<br>
    text_color: tuple = (1, 1, 1, 1)<br>
<br>
    def __post_init__(self):<br>
        if self.material is None:<br>
            raise RuntimeError(&quot;UIButton requires material for background&quot;)<br>
        if self.text_material is None:<br>
            raise RuntimeError(&quot;UIButton requires text_material for label&quot;)<br>
<br>
        self.bg = UIRectangle(<br>
            position=self.position,<br>
            size=self.size,<br>
            color=self.background_color,<br>
            material=self.material,<br>
        )<br>
<br>
        # небольшое смещение текста внутрь<br>
        text_pos = (<br>
            self.position[0] + 0.01,<br>
            self.position[1] + 0.01,<br>
        )<br>
<br>
        self.label = UIText(<br>
            text=self.text,<br>
            position=text_pos,<br>
            color=self.text_color,<br>
            scale=1.0,<br>
            material=self.text_material,<br>
        )<br>
<br>
    def contains(self, nx, ny):<br>
        return self.bg.contains(nx, ny)<br>
<br>
    def draw(self, canvas, graphics, context_key, viewport_rect):<br>
        self.bg.draw(canvas, graphics, context_key, viewport_rect)<br>
        self.label.draw(canvas, graphics, context_key, viewport_rect)<br>
<br>
@dataclass<br>
class UISlider(UIElement):<br>
    position: tuple[float, float]              # нормализовано 0..1<br>
    size: tuple[float, float]                  # ширина/высота трека<br>
    value: float = 0.5                         # 0..1<br>
    on_change: callable | None = None<br>
    material: Material | None = None<br>
    handle_material: Material | None = None<br>
<br>
    _dragging: bool = False<br>
<br>
    def _track_vertices(self):<br>
        rect = UIRectangle(<br>
            position=self.position,<br>
            size=self.size,<br>
            color=(0.3, 0.3, 0.3, 1),<br>
            material=self.material<br>
        )<br>
        return rect<br>
<br>
    def _handle_position(self):<br>
        x, y = self.position<br>
        w, h = self.size<br>
        hx = x + self.value * w<br>
        return hx, y<br>
<br>
    def draw(self, canvas, graphics, context_key, viewport_rect):<br>
        track = self._track_vertices()<br>
        track.draw(canvas, graphics, context_key, viewport_rect)<br>
<br>
        hx, hy = self._handle_position()<br>
        handle = UIRectangle(<br>
            position=(hx - 0.01, hy),<br>
            size=(0.02, self.size[1]),<br>
            color=(0.8, 0.8, 0.9, 1),<br>
            material=self.handle_material<br>
        )<br>
        handle.draw(canvas, graphics, context_key, viewport_rect)<br>
<br>
    def contains(self, nx, ny):<br>
        x, y = self.position<br>
        w, h = self.size<br>
        return x &lt;= nx &lt;= x + w and y &lt;= ny &lt;= y + h<br>
<br>
    # === Events ===<br>
    def on_mouse_down(self, x, y):<br>
        print(&quot;Slider mouse down at:&quot;, (x, y))<br>
        self._dragging = True<br>
<br>
    def on_mouse_move(self, x, y, viewport_rect):<br>
        # преобразуем в нормализованные координаты<br>
        px, py, pw, ph = viewport_rect<br>
        nx = (x - px) / pw<br>
        ny = (y - py) / ph<br>
<br>
        print(&quot;Slider mouse move at:&quot;, (nx, ny))<br>
        if not self._dragging:<br>
            return<br>
        x0, y0 = self.position<br>
        w, h = self.size<br>
        t = (nx - x0) / w<br>
        t = max(0.0, min(1.0, t))<br>
        self.value = t<br>
        if self.on_change:<br>
            self.on_change(self.value)<br>
<br>
<br>
    def on_mouse_up(self, x, y, viewport_rect):<br>
        print(&quot;Slider mouse up at:&quot;, (x, y))<br>
        self._dragging = False<br>
<!-- END SCAT CODE -->
</body>
</html>
