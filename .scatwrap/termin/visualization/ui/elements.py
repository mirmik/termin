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
&#9;&quot;&quot;&quot;Base UI element rendered inside a canvas.&quot;&quot;&quot;<br>
<br>
&#9;material: Material | None = None<br>
<br>
&#9;def draw(self, canvas, graphics, context_key: int, viewport_rect: Tuple[int, int, int, int]):<br>
&#9;&#9;raise NotImplementedError<br>
<br>
&#9;def _require_material(self) -&gt; Material:<br>
&#9;&#9;if self.material is None:<br>
&#9;&#9;&#9;raise RuntimeError(f&quot;{self.__class__.__name__} has no material assigned.&quot;)<br>
&#9;&#9;return self.material<br>
&#9;<br>
&#9;def contains(self, nx: float, ny: float) -&gt; bool:<br>
&#9;&#9;return False<br>
&#9;<br>
&#9;def on_mouse_down(self, x: float, y: float, viewport_rect):<br>
&#9;&#9;pass<br>
<br>
&#9;def on_mouse_move(self, x: float, y: float, viewport_rect):<br>
&#9;&#9;pass<br>
<br>
&#9;def on_mouse_up(self, x: float, y: float, viewport_rect):<br>
&#9;&#9;pass  <br>
<br>
<br>
@dataclass<br>
class UIRectangle(UIElement):<br>
&#9;&quot;&quot;&quot;Axis-aligned rectangle defined in normalized viewport coordinates.&quot;&quot;&quot;<br>
<br>
&#9;position: Tuple[float, float]<br>
&#9;size: Tuple[float, float]<br>
&#9;color: Tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)<br>
&#9;material: Material | None = None<br>
<br>
&#9;def _to_clip_vertices(self) -&gt; np.ndarray:<br>
&#9;&#9;x, y = self.position<br>
&#9;&#9;w, h = self.size<br>
&#9;&#9;left = x * 2.0 - 1.0<br>
&#9;&#9;right = (x + w) * 2.0 - 1.0<br>
&#9;&#9;top = 1.0 - y * 2.0<br>
&#9;&#9;bottom = 1.0 - (y + h) * 2.0<br>
&#9;&#9;return np.array(<br>
&#9;&#9;&#9;[<br>
&#9;&#9;&#9;&#9;[left, top],<br>
&#9;&#9;&#9;&#9;[right, top],<br>
&#9;&#9;&#9;&#9;[left, bottom],<br>
&#9;&#9;&#9;&#9;[right, bottom],<br>
&#9;&#9;&#9;],<br>
&#9;&#9;&#9;dtype=np.float32,<br>
&#9;&#9;)<br>
<br>
&#9;def contains(self, nx: float, ny: float) -&gt; bool:<br>
&#9;&#9;x, y = self.position<br>
&#9;&#9;w, h = self.size<br>
&#9;&#9;return x &lt;= nx &lt;= x + w and y &lt;= ny &lt;= y + h<br>
<br>
&#9;def draw(self, canvas, graphics, context_key: int, viewport_rect: Tuple[int, int, int, int]):<br>
&#9;&#9;material = self._require_material()<br>
&#9;&#9;material.apply(IDENTITY, IDENTITY, IDENTITY, graphics=graphics, context_key=context_key)<br>
&#9;&#9;vertices = self._to_clip_vertices()<br>
&#9;&#9;shader = material.shader<br>
&#9;&#9;shader.set_uniform_vec4(&quot;u_color&quot;, np.array(self.color, dtype=np.float32))<br>
&#9;&#9;shader.set_uniform_int(&quot;u_use_texture&quot;, 0)<br>
&#9;&#9;canvas.draw_vertices(graphics, context_key, vertices)<br>
<br>
<br>
@dataclass<br>
class UIText(UIElement):<br>
&#9;text: str<br>
&#9;position: tuple[float, float]<br>
&#9;color: tuple[float, float, float, float] = (1, 1, 1, 1)<br>
&#9;scale: float = 1.0<br>
&#9;material: Material | None = None<br>
<br>
&#9;def draw(self, canvas, graphics, context_key, viewport):<br>
&#9;&#9;if not hasattr(canvas, &quot;font&quot;):<br>
&#9;&#9;&#9;return<br>
&#9;&#9;material = self._require_material()<br>
&#9;&#9;material.apply(IDENTITY, IDENTITY, IDENTITY, graphics=graphics, context_key=context_key)<br>
<br>
&#9;&#9;shader = material.shader<br>
&#9;&#9;shader.set_uniform_vec4(&quot;u_color&quot;, np.array(self.color, dtype=np.float32))<br>
&#9;&#9;shader.set_uniform_int(&quot;u_use_texture&quot;, 1)<br>
&#9;&#9;texture_handle = canvas.font.ensure_texture(graphics, context_key=context_key)<br>
&#9;&#9;texture_handle.bind(0)<br>
&#9;&#9;shader.set_uniform_int(&quot;u_texture&quot;, 0)<br>
<br>
&#9;&#9;x, y = self.position<br>
&#9;&#9;px, py, pw, ph = viewport<br>
<br>
&#9;&#9;cx = x<br>
&#9;&#9;cy = y<br>
<br>
&#9;&#9;for ch in self.text:<br>
&#9;&#9;&#9;if ch not in canvas.font.glyphs:<br>
&#9;&#9;&#9;&#9;continue<br>
&#9;&#9;&#9;glyph = canvas.font.glyphs[ch]<br>
&#9;&#9;&#9;w, h = glyph[&quot;size&quot;]<br>
&#9;&#9;&#9;u0, v0, u1, v1 = glyph[&quot;uv&quot;]<br>
<br>
&#9;&#9;&#9;sx = w * self.scale / pw * 2<br>
&#9;&#9;&#9;sy = h * self.scale / ph * 2<br>
<br>
&#9;&#9;&#9;vx0 = cx * 2 - 1<br>
&#9;&#9;&#9;vy0 = 1 - cy * 2<br>
&#9;&#9;&#9;vx1 = (cx + w * self.scale / pw) * 2 - 1<br>
&#9;&#9;&#9;vy1 = 1 - (cy + h * self.scale / ph) * 2<br>
<br>
&#9;&#9;&#9;vertices = np.array([<br>
&#9;&#9;&#9;&#9;[vx0, vy0, u0, v0],<br>
&#9;&#9;&#9;&#9;[vx1, vy0, u1, v0],<br>
&#9;&#9;&#9;&#9;[vx0, vy1, u0, v1],<br>
&#9;&#9;&#9;&#9;[vx1, vy1, u1, v1],<br>
&#9;&#9;&#9;], dtype=np.float32)<br>
<br>
&#9;&#9;&#9;canvas.draw_textured_quad(graphics, context_key, vertices)<br>
<br>
&#9;&#9;&#9;cx += (w * self.scale) / pw<br>
<br>
<br>
@dataclass<br>
class UIButton(UIElement):<br>
&#9;position: tuple[float, float]<br>
&#9;size: tuple[float, float]<br>
&#9;text: str<br>
&#9;on_click: callable | None = None<br>
<br>
&#9;material: Material | None = None          # фон<br>
&#9;text_material: Material | None = None     # текст<br>
<br>
&#9;background_color: tuple = (0.2, 0.2, 0.25, 1.0)<br>
&#9;text_color: tuple = (1, 1, 1, 1)<br>
<br>
&#9;def __post_init__(self):<br>
&#9;&#9;if self.material is None:<br>
&#9;&#9;&#9;raise RuntimeError(&quot;UIButton requires material for background&quot;)<br>
&#9;&#9;if self.text_material is None:<br>
&#9;&#9;&#9;raise RuntimeError(&quot;UIButton requires text_material for label&quot;)<br>
<br>
&#9;&#9;self.bg = UIRectangle(<br>
&#9;&#9;&#9;position=self.position,<br>
&#9;&#9;&#9;size=self.size,<br>
&#9;&#9;&#9;color=self.background_color,<br>
&#9;&#9;&#9;material=self.material,<br>
&#9;&#9;)<br>
<br>
&#9;&#9;# небольшое смещение текста внутрь<br>
&#9;&#9;text_pos = (<br>
&#9;&#9;&#9;self.position[0] + 0.01,<br>
&#9;&#9;&#9;self.position[1] + 0.01,<br>
&#9;&#9;)<br>
<br>
&#9;&#9;self.label = UIText(<br>
&#9;&#9;&#9;text=self.text,<br>
&#9;&#9;&#9;position=text_pos,<br>
&#9;&#9;&#9;color=self.text_color,<br>
&#9;&#9;&#9;scale=1.0,<br>
&#9;&#9;&#9;material=self.text_material,<br>
&#9;&#9;)<br>
<br>
&#9;def contains(self, nx, ny):<br>
&#9;&#9;return self.bg.contains(nx, ny)<br>
<br>
&#9;def draw(self, canvas, graphics, context_key, viewport_rect):<br>
&#9;&#9;self.bg.draw(canvas, graphics, context_key, viewport_rect)<br>
&#9;&#9;self.label.draw(canvas, graphics, context_key, viewport_rect)<br>
<br>
@dataclass<br>
class UISlider(UIElement):<br>
&#9;position: tuple[float, float]              # нормализовано 0..1<br>
&#9;size: tuple[float, float]                  # ширина/высота трека<br>
&#9;value: float = 0.5                         # 0..1<br>
&#9;on_change: callable | None = None<br>
&#9;material: Material | None = None<br>
&#9;handle_material: Material | None = None<br>
<br>
&#9;_dragging: bool = False<br>
<br>
&#9;def _track_vertices(self):<br>
&#9;&#9;rect = UIRectangle(<br>
&#9;&#9;&#9;position=self.position,<br>
&#9;&#9;&#9;size=self.size,<br>
&#9;&#9;&#9;color=(0.3, 0.3, 0.3, 1),<br>
&#9;&#9;&#9;material=self.material<br>
&#9;&#9;)<br>
&#9;&#9;return rect<br>
<br>
&#9;def _handle_position(self):<br>
&#9;&#9;x, y = self.position<br>
&#9;&#9;w, h = self.size<br>
&#9;&#9;hx = x + self.value * w<br>
&#9;&#9;return hx, y<br>
<br>
&#9;def draw(self, canvas, graphics, context_key, viewport_rect):<br>
&#9;&#9;track = self._track_vertices()<br>
&#9;&#9;track.draw(canvas, graphics, context_key, viewport_rect)<br>
<br>
&#9;&#9;hx, hy = self._handle_position()<br>
&#9;&#9;handle = UIRectangle(<br>
&#9;&#9;&#9;position=(hx - 0.01, hy),<br>
&#9;&#9;&#9;size=(0.02, self.size[1]),<br>
&#9;&#9;&#9;color=(0.8, 0.8, 0.9, 1),<br>
&#9;&#9;&#9;material=self.handle_material<br>
&#9;&#9;)<br>
&#9;&#9;handle.draw(canvas, graphics, context_key, viewport_rect)<br>
<br>
&#9;def contains(self, nx, ny):<br>
&#9;&#9;x, y = self.position<br>
&#9;&#9;w, h = self.size<br>
&#9;&#9;return x &lt;= nx &lt;= x + w and y &lt;= ny &lt;= y + h<br>
<br>
&#9;# === Events ===<br>
&#9;def on_mouse_down(self, x, y):<br>
&#9;&#9;print(&quot;Slider mouse down at:&quot;, (x, y))<br>
&#9;&#9;self._dragging = True<br>
<br>
&#9;def on_mouse_move(self, x, y, viewport_rect):<br>
&#9;&#9;# преобразуем в нормализованные координаты<br>
&#9;&#9;px, py, pw, ph = viewport_rect<br>
&#9;&#9;nx = (x - px) / pw<br>
&#9;&#9;ny = (y - py) / ph<br>
<br>
&#9;&#9;print(&quot;Slider mouse move at:&quot;, (nx, ny))<br>
&#9;&#9;if not self._dragging:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;x0, y0 = self.position<br>
&#9;&#9;w, h = self.size<br>
&#9;&#9;t = (nx - x0) / w<br>
&#9;&#9;t = max(0.0, min(1.0, t))<br>
&#9;&#9;self.value = t<br>
&#9;&#9;if self.on_change:<br>
&#9;&#9;&#9;self.on_change(self.value)<br>
<br>
<br>
&#9;def on_mouse_up(self, x, y, viewport_rect):<br>
&#9;&#9;print(&quot;Slider mouse up at:&quot;, (x, y))<br>
&#9;&#9;self._dragging = False<br>
<!-- END SCAT CODE -->
</body>
</html>
