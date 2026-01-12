"""
ViewportRenderState — контейнер GPU ресурсов для viewport.

Хранит:
- fbos: пул FBO для ресурсов framegraph (промежуточные буферы)
- shadow_map_arrays: пул ShadowMapArrayResource
- output_fbo: финальный результат рендера viewport (для blit на дисплей)

Pipeline теперь хранится в Viewport напрямую.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, Optional, Tuple

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import FramebufferHandle, GraphicsBackend
    from termin.visualization.render.framegraph.resource import ShadowMapArrayResource


@dataclass
class ViewportRenderState:
    """
    GPU ресурсы для viewport.

    Управляет FBO пулом для framegraph ресурсов и output FBO
    для финального результата рендера.

    Атрибуты:
        fbos: Словарь {resource_name -> FramebufferHandle} для framegraph.
        shadow_map_arrays: Словарь {resource_name -> ShadowMapArrayResource}.
        output_fbo: FBO с финальным результатом рендера (для blit на дисплей).
    """
    fbos: Dict[str, "FramebufferHandle"] = field(default_factory=dict)
    shadow_map_arrays: Dict[str, "ShadowMapArrayResource"] = field(default_factory=dict)

    # Output FBO - финальный результат рендера viewport
    output_fbo: Optional["FramebufferHandle"] = None
    _output_size: Tuple[int, int] = (0, 0)

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
        Удаляет все ресурсы из пула.

        Вызывает delete() для каждого ресурса.
        """
        from termin._native import log

        for name, resource in self.fbos.items():
            if resource is not None:
                try:
                    resource.delete()
                except Exception as e:
                    log.warn(f"[ViewportRenderState] Failed to delete FBO '{name}': {e}")
        self.fbos.clear()

        # Очищаем shadow_map_arrays (FBO принадлежат C++ ShadowPass, не удаляем)
        self.shadow_map_arrays.clear()

    def get_shadow_map_array(self, name: str) -> Optional["ShadowMapArrayResource"]:
        """Возвращает ShadowMapArrayResource по имени ресурса."""
        return self.shadow_map_arrays.get(name)

    def set_shadow_map_array(self, name: str, resource: "ShadowMapArrayResource") -> None:
        """Устанавливает ShadowMapArrayResource для ресурса."""
        self.shadow_map_arrays[name] = resource

    def ensure_output_fbo(
        self,
        graphics: "GraphicsBackend",
        size: Tuple[int, int],
    ) -> "FramebufferHandle":
        """
        Создаёт или ресайзит output FBO под нужный размер.

        Output FBO используется для финального результата рендера viewport.
        После рендеринга содержимое блитается на дисплей.

        Параметры:
            graphics: GraphicsBackend для создания FBO.
            size: Требуемый размер (width, height).

        Возвращает:
            FramebufferHandle нужного размера.
        """
        if self.output_fbo is None:
            self.output_fbo = graphics.create_framebuffer(size)
            self._output_size = size
        elif self._output_size != size:
            self.output_fbo.resize(size)
            self._output_size = size
        return self.output_fbo

    def clear_all(self) -> None:
        """
        Освобождает все ресурсы включая output_fbo.

        Вызывайте при удалении viewport.
        """
        self.clear_fbos()

        if self.output_fbo is not None:
            try:
                self.output_fbo.delete()
            except Exception as e:
                from termin._native import log
                log.warn(f"[ViewportRenderState] Failed to delete output_fbo: {e}")
            self.output_fbo = None
            self._output_size = (0, 0)
