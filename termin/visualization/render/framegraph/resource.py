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
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Tuple

import numpy as np

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import FramebufferHandle, GPUTextureHandle


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


@dataclass
class ShadowMapArrayEntry:
    """
    Данные одного shadow map для одного источника света (или каскада).

    Атрибуты:
        fbo: FBO, в который рендерится shadow map
        light_space_matrix: матрица P * V для преобразования мировых координат
                           в clip-пространство источника света
        light_index: индекс источника в scene.lights
        cascade_index: индекс каскада (0-3), 0 для не-каскадных теней
        cascade_split_near: начало каскада (view-space Z)
        cascade_split_far: конец каскада (view-space Z)

    Формула преобразования точки p в shadow map координаты:
        p_light_clip = light_space_matrix @ [p.x, p.y, p.z, 1]^T
        uv = (p_light_clip.xy / p_light_clip.w) * 0.5 + 0.5
        depth_from_light = p_light_clip.z / p_light_clip.w
    """
    fbo: "FramebufferHandle"
    light_space_matrix: np.ndarray
    light_index: int
    cascade_index: int = 0
    cascade_split_near: float = 0.0
    cascade_split_far: float = 0.0

    def texture(self) -> "GPUTextureHandle":
        """Возвращает color-текстуру FBO."""
        return self.fbo.color_texture()


@dataclass
class ShadowMapArrayResource(FrameGraphResource):
    """
    Массив shadow maps для всех источников света с тенями.
    
    Это ресурс framegraph, который ShadowPass создаёт и записывает,
    а ColorPass читает.
    
    Атрибуты:
        entries: список ShadowMapArrayEntry, по одному на источник
        resolution: разрешение каждого shadow map (квадратное)
    """
    entries: List[ShadowMapArrayEntry] = field(default_factory=list)
    resolution: int = 1024

    @property
    def resource_type(self) -> str:
        return "shadow_map_array"

    def __len__(self) -> int:
        return len(self.entries)

    def __getitem__(self, index: int) -> ShadowMapArrayEntry:
        return self.entries[index]

    def __iter__(self):
        return iter(self.entries)

    def add_entry(
        self,
        fbo: "FramebufferHandle",
        light_space_matrix: np.ndarray,
        light_index: int,
        cascade_index: int = 0,
        cascade_split_near: float = 0.0,
        cascade_split_far: float = 0.0,
    ) -> None:
        """Добавляет запись для нового источника света (или каскада)."""
        self.entries.append(ShadowMapArrayEntry(
            fbo=fbo,
            light_space_matrix=light_space_matrix,
            light_index=light_index,
            cascade_index=cascade_index,
            cascade_split_near=cascade_split_near,
            cascade_split_far=cascade_split_far,
        ))

    def clear(self) -> None:
        """Очищает массив (FBO не удаляются, только ссылки)."""
        self.entries.clear()

    def get_by_light_index(self, light_index: int) -> ShadowMapArrayEntry | None:
        """Находит entry по индексу источника света."""
        for entry in self.entries:
            if entry.light_index == light_index:
                return entry
        return None

    def resize(self, size: Tuple[int, int]) -> None:
        """
        No-op для совместимости с интерфейсом FBO.

        Shadow maps имеют собственное разрешение (self.resolution),
        которое не зависит от размера viewport'а.
        Изменение размера отдельных FBO происходит в ShadowPass.
        """
        pass

    def delete(self) -> None:
        """Очищает entries. FBO не удаляются — они принадлежат C++ ShadowPass::fbo_pool_."""
        self.entries.clear()
