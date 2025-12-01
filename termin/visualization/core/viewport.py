from dataclasses import dataclass, field
from typing import List, Optional, Tuple, TYPE_CHECKING

from termin.visualization.core.scene import Scene
from termin.visualization.core.camera import CameraComponent

if TYPE_CHECKING:
    from termin.visualization.render.framegraph import RenderPipeline
    from termin.visualization.render.framegraph.core import FramePass


@dataclass
class Viewport:
    scene: Scene
    camera: CameraComponent
    window: "Window"
    rect: Tuple[float, float, float, float] # x, y, width, height in normalized coords (0.0:1.0)
    canvas: Optional["Canvas"] = None
    pipeline: "RenderPipeline | None" = None
    fbos: dict = field(default_factory=dict)


    def screen_point_to_ray(self, x, y):
        # окно → прямоугольник вьюпорта в пикселях
        rect = self.window.viewport_rect_to_pixels(self)

        # вызываем камеру
        return self.camera.screen_point_to_ray(x, y, viewport_rect=rect)

    def set_render_pipeline(self, pipeline: "RenderPipeline"):
        """
        Устанавливает конвейер рендера для этого вьюпорта.
        """
        self.pipeline = pipeline

    def find_render_pass(self, pass_name: str) -> Optional["FramePass"]:
        """
        Ищет в конвейере рендера пасс с заданным именем.

        Возвращает FramePass или None.
        """
        if self.pipeline is None:
            return None
        for p in self.pipeline.passes:
            if p.pass_name == pass_name:
                return p
        return None

    # -------------------------------------------------------------
    #     ДЕФОЛТНЫЙ ПАЙПЛАЙН ДЛЯ ВЬЮПОРТА
    # -------------------------------------------------------------
    @staticmethod
    def make_default_pipeline() -> "RenderPipeline":
        """
        Собирает дефолтный конвейер рендера для этого вьюпорта.
        """
        from termin.visualization.render.framegraph import (
            CanvasPass,
            ColorPass,
            IdPass,
            PresentToScreenPass,
            RenderPipeline,
            ClearSpec,
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
        
        clear_specs = [
            ClearSpec(resource="empty", color=(0.2, 0.2, 0.2, 1.0), depth=1.0),
        ]
        
        return RenderPipeline(passes=passes, clear_specs=clear_specs)
