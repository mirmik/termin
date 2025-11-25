
from dataclasses import dataclass, field
from typing import Optional, Tuple
from .scene import Scene
from .camera import CameraComponent

@dataclass
class Viewport:
    scene: Scene
    camera: CameraComponent
    window: "Window"
    rect: Tuple[float, float, float, float] # x, y, width, height in normalized coords (0.0:1.0)
    canvas: Optional["Canvas"] = None
    postprocess: list["PostProcessEffect"] = field(default_factory=list)
    frame_passes: list["FramePass"] = field(default_factory=list)


    def screen_point_to_ray(self, x, y):
        # окно → прямоугольник вьюпорта в пикселях
        rect = self.window.viewport_rect_to_pixels(self)

        # вызываем камеру
        return self.camera.screen_point_to_ray(x, y, viewport_rect=rect)

    def add_postprocess(self, effect: "PostProcessEffect"):
        self.postprocess.append(effect)