"""
ViewportRenderState — контейнер GPU ресурсов для viewport.

Хранит:
- fbos: пул FBO для ресурсов framegraph
- shadow_map_arrays: пул ShadowMapArrayResource

Pipeline теперь хранится в Viewport напрямую.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import FramebufferHandle
    from termin.visualization.render.framegraph.resource import ShadowMapArrayResource


@dataclass
class ViewportRenderState:
    """
    GPU ресурсы для viewport.

    Управляет FBO пулом для framegraph ресурсов.

    Атрибуты:
        fbos: Словарь {resource_name -> FramebufferHandle} для framegraph.
        shadow_map_arrays: Словарь {resource_name -> ShadowMapArrayResource}.
    """
    fbos: Dict[str, "FramebufferHandle"] = field(default_factory=dict)
    shadow_map_arrays: Dict[str, "ShadowMapArrayResource"] = field(default_factory=dict)

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
        for resource in self.fbos.values():
            if resource is not None:
                resource.delete()
        self.fbos.clear()

    def get_shadow_map_array(self, name: str) -> Optional["ShadowMapArrayResource"]:
        """Возвращает ShadowMapArrayResource по имени ресурса."""
        return self.shadow_map_arrays.get(name)

    def set_shadow_map_array(self, name: str, resource: "ShadowMapArrayResource") -> None:
        """Устанавливает ShadowMapArrayResource для ресурса."""
        self.shadow_map_arrays[name] = resource
