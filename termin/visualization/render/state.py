"""
ViewportRenderState — контейнер состояния рендеринга для view.

Хранит:
- pipeline: RenderPipeline (как рендерим)
- fbos: пул FBO для ресурсов framegraph

Это позволяет отделить "что рендерим" (RenderView) от "как рендерим" (ViewportRenderState).
Один RenderView может быть отрендерен разными pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from termin.visualization.render.framegraph import RenderPipeline
    from termin.visualization.platform.backends.base import FramebufferHandle


@dataclass
class ViewportRenderState:
    """
    Состояние рендеринга для RenderView.
    
    Связывает RenderView с конкретным pipeline и управляет FBO пулом.
    
    Атрибуты:
        pipeline: Конвейер рендеринга (список пассов, спецификации очистки).
        fbos: Словарь {resource_name -> FramebufferHandle} для framegraph.
    """
    pipeline: Optional["RenderPipeline"] = None
    fbos: Dict[str, "FramebufferHandle"] = field(default_factory=dict)

    def get_fbo(self, name: str) -> Optional["FramebufferHandle"]:
        """
        Возвращает FBO по имени ресурса.
        
        Параметры:
            name: Имя ресурса framegraph.
        
        Возвращает:
            FramebufferHandle или None.
        """
        return self.fbos.get(name)

    def set_fbo(self, name: str, fbo: "FramebufferHandle") -> None:
        """
        Устанавливает FBO для ресурса.
        
        Параметры:
            name: Имя ресурса framegraph.
            fbo: Хэндл фреймбуфера.
        """
        self.fbos[name] = fbo

    def clear_fbos(self) -> None:
        """
        Удаляет все FBO из пула.
        
        Вызывает delete() для каждого FBO перед удалением из словаря.
        """
        for fbo in self.fbos.values():
            if fbo is not None:
                fbo.delete()
        self.fbos.clear()
