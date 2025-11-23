
from dataclasses import dataclass, field
from typing import Optional, Tuple
from .scene import Scene
from .camera import CameraComponent

@dataclass
class Viewport:
    scene: Scene
    camera: CameraComponent
    window: "Window"
    rect: Tuple[float, float, float, float]
    canvas: Optional["Canvas"] = None
    postprocess: list["PostProcessEffect"] = field(default_factory=list)


    def screen_point_to_ray(self, x, y):
        # окно → прямоугольник вьюпорта в пикселях
        rect = self.window.viewport_rect_to_pixels(self)

        # вызываем камеру
        return self.camera.screen_point_to_ray(x, y, viewport_rect=rect)