from dataclasses import dataclass, field
from typing import List, Optional, Tuple, TYPE_CHECKING

from termin.visualization.core.scene import Scene
from termin.visualization.core.camera import CameraComponent

if TYPE_CHECKING:
    from termin.visualization.core.display import Display
    from termin.visualization.ui.canvas import Canvas


@dataclass
class Viewport:
    """
    Viewport — "что рендерим и куда" в рамках дисплея.

    Содержит только данные:
    - scene: сцена с объектами
    - camera: камера для рендеринга
    - display: родительский дисплей
    - rect: нормализованный прямоугольник (x, y, w, h) в [0..1]
    - canvas: опциональная 2D канва для UI

    НЕ содержит:
    - pipeline (управляется снаружи)
    - fbos (управляются снаружи через ViewportRenderState)

    Для рендеринга используйте RenderEngine с RenderView и ViewportRenderState.
    """
    scene: Scene
    camera: CameraComponent
    rect: Tuple[float, float, float, float]  # x, y, width, height in normalized coords (0.0:1.0)
    display: Optional["Display"] = None
    canvas: Optional["Canvas"] = None

    def screen_point_to_ray(self, x: float, y: float):
        """
        Преобразует экранные координаты в луч в мировом пространстве.

        Параметры:
            x, y: координаты в пикселях окна.

        Возвращает:
            Ray3 из камеры через указанную точку.
        """
        if self.display is None:
            raise ValueError("Viewport has no display")
        rect = self.display.viewport_rect_to_pixels(self)
        return self.camera.screen_point_to_ray(x, y, viewport_rect=rect)

    def compute_pixel_rect(self, width: int, height: int) -> Tuple[int, int, int, int]:
        """
        Вычисляет прямоугольник viewport'а в пикселях.

        Параметры:
            width, height: размер родительской поверхности.

        Возвращает:
            (px, py, pw, ph) — позиция и размер в пикселях.
        """
        vx, vy, vw, vh = self.rect
        px = int(vx * width)
        py = int(vy * height)
        pw = max(1, int(vw * width))
        ph = max(1, int(vh * height))
        return (px, py, pw, ph)


def make_default_pipeline() -> "RenderPipeline":
    """
    Собирает дефолтный конвейер рендера.

    Вынесено из класса Viewport как свободная функция.
    """
    from termin.visualization.render.framegraph import (
        CanvasPass,
        ColorPass,
        PresentToScreenPass,
        RenderPipeline
    )
    from termin.visualization.render.framegraph.passes.skybox import SkyBoxPass
    from termin.visualization.render.postprocess import PostProcessPass

    passes: List = [
        SkyBoxPass(input_res="empty", output_res="skybox", pass_name="Skybox"),
        ColorPass(input_res="skybox", output_res="color", shadow_res=None, pass_name="Color"),
        PostProcessPass(
            effects=[],
            input_res="color",
            output_res="color_pp",
            pass_name="PostFX",
        ),
        CanvasPass(
            src="color_pp",
            dst="color+ui",
            pass_name="Canvas",
        ),
        PresentToScreenPass(
            input_res="color+ui",
            pass_name="Present",
        )
    ]

    return RenderPipeline(passes=passes)