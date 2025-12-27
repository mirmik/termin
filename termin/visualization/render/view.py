"""
RenderView — описание "что рендерим" без привязки к конкретному окну.

RenderView содержит:
- scene: сцена с объектами
- camera: камера (CameraComponent)
- rect: нормализованный прямоугольник [0..1] внутри целевой поверхности
- canvas: опциональная 2D канва для UI
- pipeline: конвейер рендеринга

RenderView НЕ содержит:
- fbos (это ViewportRenderState)
- ссылки на Window

Это позволяет использовать один RenderView для разных целей:
- рендер в окно
- offscreen рендер
- рендер в текстуру для превью

Формула преобразования rect → пиксели:
    px = rect.x * surface_width
    py = rect.y * surface_height
    pw = rect.w * surface_width
    ph = rect.h * surface_height
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.camera import CameraComponent
    from termin.visualization.ui.canvas import Canvas
    from termin.visualization.render.framegraph import RenderPipeline


@dataclass
class RenderView:
    """
    Описание "что рендерим" для RenderEngine.

    Атрибуты:
        scene: Сцена с объектами для рендеринга.
        camera: Камера, определяющая точку зрения.
        rect: Нормализованный прямоугольник (x, y, w, h) в [0..1].
              (0,0) — левый нижний угол, (1,1) — правый верхний.
        canvas: Опциональная 2D канва для overlay UI.
        pipeline: Конвейер рендеринга.
    """
    scene: "Scene"
    camera: "CameraComponent"
    rect: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)
    canvas: Optional["Canvas"] = None
    pipeline: Optional["RenderPipeline"] = None

    def compute_pixel_rect(
        self, 
        surface_width: int, 
        surface_height: int
    ) -> Tuple[int, int, int, int]:
        """
        Вычисляет прямоугольник в пикселях для заданного размера поверхности.
        
        Формула:
            px = rect.x * width
            py = rect.y * height  
            pw = rect.w * width
            ph = rect.h * height
        
        Параметры:
            surface_width: Ширина поверхности в пикселях.
            surface_height: Высота поверхности в пикселях.
        
        Возвращает:
            Кортеж (px, py, pw, ph) — позиция и размер в пикселях.
        """
        vx, vy, vw, vh = self.rect
        px = int(vx * surface_width)
        py = int(vy * surface_height)
        pw = max(1, int(vw * surface_width))
        ph = max(1, int(vh * surface_height))
        return (px, py, pw, ph)
