from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from termin.visualization.core.scene import Scene
from termin.visualization.core.camera import CameraComponent

@dataclass
class Viewport:
    scene: Scene
    camera: CameraComponent
    window: "Window"
    rect: Tuple[float, float, float, float] # x, y, width, height in normalized coords (0.0:1.0)
    canvas: Optional["Canvas"] = None
    frame_passes: list["FramePass"] = field(default_factory=list)
    fbos: dict = field(default_factory=dict)


    def screen_point_to_ray(self, x, y):
        # окно → прямоугольник вьюпорта в пикселях
        rect = self.window.viewport_rect_to_pixels(self)

        # вызываем камеру
        return self.camera.screen_point_to_ray(x, y, viewport_rect=rect)

    def set_render_pipeline(self, passes: list["FramePass"]):
        """
        Устанавливает конвейер рендера для этого вьюпорта.

        passes – список FramePass.
        """
        self.frame_passes = passes

    def find_render_pass(self, pass_name: str) -> Optional["FramePass"]:
        """
        Ищет в конвейере рендера пасс с заданным именем.

        Возвращает FramePass или None.
        """
        for p in self.frame_passes:
            if p.pass_name == pass_name:
                return p
        return None

    # -------------------------------------------------------------
    #     ДЕФОЛТНЫЙ ПАЙПЛАЙН ДЛЯ ВЬЮПОРТА
    # -------------------------------------------------------------
    @staticmethod
    def make_default_pipeline() -> list["FramePass"]:
        """
        Собирает дефолтный конвейер рендера для этого вьюпорта.
        """
        from termin.visualization.render.framegraph import (
            CanvasPass,
            ColorPass,
            IdPass,
            PresentToScreenPass,
        )
        from termin.visualization.render.postprocess import PostProcessPass

        passes: List["FramePass"] = [
            ColorPass(input_res="empty", output_res="color", pass_name="Color"),
            PostProcessPass(
                effects=[],  # можно заранее что-то положить сюда
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
        return passes
