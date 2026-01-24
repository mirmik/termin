"""
Иерархия ресурсов framegraph.

FrameGraphResource — базовый класс для всех ресурсов конвейера.
Ресурсы передаются между пассами через reads/writes.

Типы ресурсов:
- SingleFBO: обёртка над одним framebuffer'ом
- ShadowMapArray: массив shadow maps для освещения

Алиасы (inplace):
    При inplace-операции ресурс читается и пишется одновременно.
    Для этого используется пара алиасов (read_name, write_name),
    которые ссылаются на один и тот же физический ресурс.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Tuple

from termin._native.render import (
    ShadowMapArrayEntry,
    ShadowMapArrayResource,
)

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import FramebufferHandle, GPUTextureHandle

__all__ = [
    "FrameGraphResource",
    "SingleFBO",
    "ShadowMapArrayEntry",
    "ShadowMapArrayResource",
]


class FrameGraphResource(ABC):
    """
    Базовый класс для ресурсов framegraph.

    Каждый ресурс имеет тип (resource_type), по которому
    RenderEngine определяет, как с ним работать.
    """

    @property
    @abstractmethod
    def resource_type(self) -> str:
        """Тип ресурса для идентификации в pipeline."""
        ...


@dataclass
class SingleFBO(FrameGraphResource):
    """
    Обёртка над одним framebuffer'ом.
    
    Это стандартный тип ресурса для большинства пассов:
    color pass, depth pass, id pass и т.д.
    
    Атрибуты:
        fbo: handle на framebuffer
        size: размер (width, height) или None для автоматического
    """
    fbo: "FramebufferHandle"
    size: Tuple[int, int] | None = None

    @property
    def resource_type(self) -> str:
        return "fbo"

    def color_texture(self) -> "GPUTextureHandle":
        """Возвращает color attachment как текстуру."""
        return self.fbo.color_texture()

    def depth_texture(self) -> "GPUTextureHandle | None":
        """Возвращает depth attachment как текстуру (если есть)."""
        return self.fbo.depth_texture()

    def resize(self, size: Tuple[int, int]) -> None:
        """Изменяет размер framebuffer'а."""
        self.fbo.resize(size)
        self.size = size

    def get_size(self) -> Tuple[int, int]:
        """Возвращает текущий размер."""
        if self.size is not None:
            return self.size
        return self.fbo.get_size()


