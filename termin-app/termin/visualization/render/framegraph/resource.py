"""
Иерархия ресурсов framegraph.

FrameGraphResource — базовый класс для всех ресурсов конвейера.
Ресурсы передаются между пассами через reads/writes.

Типы ресурсов:
- ShadowMapArray: массив shadow maps для освещения
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from termin._native.render import (
    ShadowMapArrayEntry,
    ShadowMapArrayResource,
)

__all__ = [
    "FrameGraphResource",
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
