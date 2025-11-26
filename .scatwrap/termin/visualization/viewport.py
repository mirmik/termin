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
    scene: Scene<br>
    camera: CameraComponent<br>
    window: &quot;Window&quot;<br>
    rect: Tuple[float, float, float, float] # x, y, width, height in normalized coords (0.0:1.0)<br>
    canvas: Optional[&quot;Canvas&quot;] = None<br>
    frame_passes: list[&quot;FramePass&quot;] = field(default_factory=list)<br>
<br>
<br>
    def screen_point_to_ray(self, x, y):<br>
        # окно → прямоугольник вьюпорта в пикселях<br>
        rect = self.window.viewport_rect_to_pixels(self)<br>
<br>
        # вызываем камеру<br>
        return self.camera.screen_point_to_ray(x, y, viewport_rect=rect)<br>
<br>
    def set_render_pipeline(self, passes: list[&quot;FramePass&quot;]):<br>
        &quot;&quot;&quot;<br>
        Устанавливает конвейер рендера для этого вьюпорта.<br>
<br>
        passes – список FramePass.<br>
        &quot;&quot;&quot;<br>
        self.frame_passes = passes<br>
<br>
    def find_render_pass(self, pass_name: str) -&gt; Optional[&quot;FramePass&quot;]:<br>
        &quot;&quot;&quot;<br>
        Ищет в конвейере рендера пасс с заданным именем.<br>
<br>
        Возвращает FramePass или None.<br>
        &quot;&quot;&quot;<br>
        for p in self.frame_passes:<br>
            if p.pass_name == pass_name:<br>
                return p<br>
        return None<br>
<br>
    # -------------------------------------------------------------<br>
    #     ДЕФОЛТНЫЙ ПАЙПЛАЙН ДЛЯ ВЬЮПОРТА<br>
    # -------------------------------------------------------------<br>
    @staticmethod<br>
    def make_default_pipeline() -&gt; list[&quot;FramePass&quot;]:<br>
        &quot;&quot;&quot;<br>
        Собирает дефолтный конвейер рендера для этого вьюпорта.<br>
        &quot;&quot;&quot;<br>
        from .framegraph import ColorPass, IdPass, CanvasPass, PresentToScreenPass<br>
        from .postprocess import PostProcessPass<br>
<br>
        passes: List[&quot;FramePass&quot;] = [<br>
            ColorPass(input_res=&quot;empty&quot;, output_res=&quot;color&quot;, pass_name=&quot;Color&quot;),<br>
            PostProcessPass(<br>
                effects=[],  # можно заранее что-то положить сюда<br>
                input_res=&quot;color&quot;,<br>
                output_res=&quot;color_pp&quot;,<br>
                pass_name=&quot;PostFX&quot;,<br>
            ),<br>
            CanvasPass(<br>
                src=&quot;color_pp&quot;,<br>
                dst=&quot;color+ui&quot;,<br>
                pass_name=&quot;Canvas&quot;,<br>
            ),<br>
            PresentToScreenPass(<br>
                input_res=&quot;color+ui&quot;,<br>
                pass_name=&quot;Present&quot;,<br>
            )<br>
        ]<br>
        return passes<br>
<!-- END SCAT CODE -->
</body>
</html>
