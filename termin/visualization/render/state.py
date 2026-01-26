"""
ViewportRenderState — контейнер GPU ресурсов для viewport.

Хранит:
- output_fbo: финальный результат рендера viewport (для blit на дисплей)
- fbos: deprecated, используется только Python RenderEngine (streaming, mesh preview)

Pipeline и FBO pool для основного рендера хранятся в RenderPipeline (C++).
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

    Управляет output FBO для финального результата рендера.
    FBO pool для основного рендера хранится в RenderPipeline (C++).

    Атрибуты:
        output_fbo: FBO с финальным результатом рендера (для blit на дисплей).
        fbos: DEPRECATED - используется только Python RenderEngine.
        shadow_map_arrays: DEPRECATED - используется только Python RenderEngine.
    """
    # Output FBO - финальный результат рендера viewport
    output_fbo: Optional["FramebufferHandle"] = None
    _output_size: Tuple[int, int] = (0, 0)

    # DEPRECATED: используется только Python RenderEngine (streaming, mesh preview)
    # Основной рендер использует RenderPipeline.fbo_pool() (C++)
    fbos: Dict[str, "FramebufferHandle"] = field(default_factory=dict)
    shadow_map_arrays: Dict[str, "ShadowMapArrayResource"] = field(default_factory=dict)

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

    # DEPRECATED methods for Python RenderEngine compatibility
    def get_shadow_map_array(self, name: str) -> Optional["ShadowMapArrayResource"]:
        """DEPRECATED: используется только Python RenderEngine."""
        return self.shadow_map_arrays.get(name)

    def set_shadow_map_array(self, name: str, resource: "ShadowMapArrayResource") -> None:
        """DEPRECATED: используется только Python RenderEngine."""
        self.shadow_map_arrays[name] = resource

    def clear_all(self) -> None:
        """
        Освобождает все ресурсы включая output_fbo.

        Вызывайте при удалении viewport.
        """
        # Clear deprecated fbos
        from termin._native import log
        for name, resource in self.fbos.items():
            if resource is not None:
                try:
                    resource.delete()
                except Exception as e:
                    log.warn(f"[ViewportRenderState] Failed to delete FBO '{name}': {e}")
        self.fbos.clear()
        self.shadow_map_arrays.clear()

        # Clear output_fbo
        if self.output_fbo is not None:
            try:
                self.output_fbo.delete()
            except Exception as e:
                log.warn(f"[ViewportRenderState] Failed to delete output_fbo: {e}")
            self.output_fbo = None
            self._output_size = (0, 0)
