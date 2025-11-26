<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/viewport.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
<br>
from dataclasses import dataclass, field<br>
from typing import Optional, Tuple<br>
from .scene import Scene<br>
from .camera import CameraComponent<br>
<br>
@dataclass<br>
class Viewport:<br>
&#9;scene: Scene<br>
&#9;camera: CameraComponent<br>
&#9;window: &quot;Window&quot;<br>
&#9;rect: Tuple[float, float, float, float] # x, y, width, height in normalized coords (0.0:1.0)<br>
&#9;canvas: Optional[&quot;Canvas&quot;] = None<br>
&#9;frame_passes: list[&quot;FramePass&quot;] = field(default_factory=list)<br>
<br>
<br>
&#9;def screen_point_to_ray(self, x, y):<br>
&#9;&#9;# окно → прямоугольник вьюпорта в пикселях<br>
&#9;&#9;rect = self.window.viewport_rect_to_pixels(self)<br>
<br>
&#9;&#9;# вызываем камеру<br>
&#9;&#9;return self.camera.screen_point_to_ray(x, y, viewport_rect=rect)<br>
<br>
&#9;def set_render_pipeline(self, passes: list[&quot;FramePass&quot;]):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Устанавливает конвейер рендера для этого вьюпорта.<br>
<br>
&#9;&#9;passes – список FramePass.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.frame_passes = passes<br>
<br>
&#9;def find_render_pass(self, pass_name: str) -&gt; Optional[&quot;FramePass&quot;]:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Ищет в конвейере рендера пасс с заданным именем.<br>
<br>
&#9;&#9;Возвращает FramePass или None.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;for p in self.frame_passes:<br>
&#9;&#9;&#9;if p.pass_name == pass_name:<br>
&#9;&#9;&#9;&#9;return p<br>
&#9;&#9;return None<br>
<br>
&#9;# -------------------------------------------------------------<br>
&#9;#     ДЕФОЛТНЫЙ ПАЙПЛАЙН ДЛЯ ВЬЮПОРТА<br>
&#9;# -------------------------------------------------------------<br>
&#9;@staticmethod<br>
&#9;def make_default_pipeline() -&gt; list[&quot;FramePass&quot;]:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Собирает дефолтный конвейер рендера для этого вьюпорта.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;from .framegraph import ColorPass, IdPass, CanvasPass, PresentToScreenPass<br>
&#9;&#9;from .postprocess import PostProcessPass<br>
<br>
&#9;&#9;passes: List[&quot;FramePass&quot;] = [<br>
&#9;&#9;&#9;ColorPass(input_res=&quot;empty&quot;, output_res=&quot;color&quot;, pass_name=&quot;Color&quot;),<br>
&#9;&#9;&#9;PostProcessPass(<br>
&#9;&#9;&#9;&#9;effects=[],  # можно заранее что-то положить сюда<br>
&#9;&#9;&#9;&#9;input_res=&quot;color&quot;,<br>
&#9;&#9;&#9;&#9;output_res=&quot;color_pp&quot;,<br>
&#9;&#9;&#9;&#9;pass_name=&quot;PostFX&quot;,<br>
&#9;&#9;&#9;),<br>
&#9;&#9;&#9;CanvasPass(<br>
&#9;&#9;&#9;&#9;src=&quot;color_pp&quot;,<br>
&#9;&#9;&#9;&#9;dst=&quot;color+ui&quot;,<br>
&#9;&#9;&#9;&#9;pass_name=&quot;Canvas&quot;,<br>
&#9;&#9;&#9;),<br>
&#9;&#9;&#9;PresentToScreenPass(<br>
&#9;&#9;&#9;&#9;input_res=&quot;color+ui&quot;,<br>
&#9;&#9;&#9;&#9;pass_name=&quot;Present&quot;,<br>
&#9;&#9;&#9;)<br>
&#9;&#9;]<br>
&#9;&#9;return passes<br>
<!-- END SCAT CODE -->
</body>
</html>
