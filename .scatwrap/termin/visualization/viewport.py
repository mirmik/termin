<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/viewport.py</title>
</head>
<body>
<pre><code>

from dataclasses import dataclass, field
from typing import Optional, Tuple
from .scene import Scene
from .camera import CameraComponent

@dataclass
class Viewport:
    scene: Scene
    camera: CameraComponent
    window: &quot;Window&quot;
    rect: Tuple[float, float, float, float] # x, y, width, height in normalized coords (0.0:1.0)
    canvas: Optional[&quot;Canvas&quot;] = None
    frame_passes: list[&quot;FramePass&quot;] = field(default_factory=list)


    def screen_point_to_ray(self, x, y):
        # окно → прямоугольник вьюпорта в пикселях
        rect = self.window.viewport_rect_to_pixels(self)

        # вызываем камеру
        return self.camera.screen_point_to_ray(x, y, viewport_rect=rect)

    def set_render_pipeline(self, passes: list[&quot;FramePass&quot;]):
        &quot;&quot;&quot;
        Устанавливает конвейер рендера для этого вьюпорта.

        passes – список FramePass.
        &quot;&quot;&quot;
        self.frame_passes = passes

    def find_render_pass(self, pass_name: str) -&gt; Optional[&quot;FramePass&quot;]:
        &quot;&quot;&quot;
        Ищет в конвейере рендера пасс с заданным именем.

        Возвращает FramePass или None.
        &quot;&quot;&quot;
        for p in self.frame_passes:
            if p.pass_name == pass_name:
                return p
        return None

    # -------------------------------------------------------------
    #     ДЕФОЛТНЫЙ ПАЙПЛАЙН ДЛЯ ВЬЮПОРТА
    # -------------------------------------------------------------
    @staticmethod
    def make_default_pipeline() -&gt; list[&quot;FramePass&quot;]:
        &quot;&quot;&quot;
        Собирает дефолтный конвейер рендера для этого вьюпорта.
        &quot;&quot;&quot;
        from .framegraph import ColorPass, IdPass, CanvasPass, PresentToScreenPass
        from .postprocess import PostProcessPass

        passes: List[&quot;FramePass&quot;] = [
            ColorPass(input_res=&quot;empty&quot;, output_res=&quot;color&quot;, pass_name=&quot;Color&quot;),
            PostProcessPass(
                effects=[],  # можно заранее что-то положить сюда
                input_res=&quot;color&quot;,
                output_res=&quot;color_pp&quot;,
                pass_name=&quot;PostFX&quot;,
            ),
            CanvasPass(
                src=&quot;color_pp&quot;,
                dst=&quot;color+ui&quot;,
                pass_name=&quot;Canvas&quot;,
            ),
            PresentToScreenPass(
                input_res=&quot;color+ui&quot;,
                pass_name=&quot;Present&quot;,
            )
        ]
        return passes
</code></pre>
</body>
</html>
