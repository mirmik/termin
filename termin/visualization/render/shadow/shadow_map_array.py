"""
ShadowMapArray — ресурс конвейера для передачи shadow maps между пассами.

Содержит массив shadow map'ов для всех источников света, отбрасывающих тени.
Каждый элемент связывает текстуру с матрицей light-space и индексом источника.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import TextureHandle, FramebufferHandle


@dataclass
class ShadowMapEntry:
    """
    Данные одного shadow map для одного источника света.
    
    Атрибуты:
        fbo: FBO, в который рендерится shadow map
        light_space_matrix: матрица P * V для преобразования мировых координат
                           в clip-пространство источника света
        light_index: индекс источника в scene.lights (для соответствия uniform'ам)
    
    Формула преобразования точки p в shadow map координаты:
        p_light_clip = light_space_matrix @ [p.x, p.y, p.z, 1]^T
        uv = (p_light_clip.xy / p_light_clip.w) * 0.5 + 0.5
        depth_from_light = p_light_clip.z / p_light_clip.w
    """
    fbo: "FramebufferHandle"
    light_space_matrix: np.ndarray
    light_index: int

    def texture(self) -> "TextureHandle":
        """Возвращает color-текстуру FBO (содержит глубину в RGB)."""
        return self.fbo.color_texture()


@dataclass
class ShadowMapArray:
    """
    Массив shadow maps для всех источников света с тенями.
    
    Это ресурс конвейера (framegraph resource), который ShadowPass
    создаёт и записывает, а ColorPass читает.
    
    Атрибуты:
        entries: список ShadowMapEntry, по одному на источник света
        resolution: разрешение каждого shadow map (квадратное)
    """
    entries: List[ShadowMapEntry] = field(default_factory=list)
    resolution: int = 1024

    def __len__(self) -> int:
        return len(self.entries)

    def __getitem__(self, index: int) -> ShadowMapEntry:
        return self.entries[index]

    def __iter__(self):
        return iter(self.entries)

    def add_entry(
        self,
        fbo: "FramebufferHandle",
        light_space_matrix: np.ndarray,
        light_index: int,
    ) -> None:
        """Добавляет запись для нового источника света."""
        self.entries.append(ShadowMapEntry(
            fbo=fbo,
            light_space_matrix=light_space_matrix,
            light_index=light_index,
        ))

    def clear(self) -> None:
        """Очищает массив (FBO не удаляются, только ссылки)."""
        self.entries.clear()

    def get_by_light_index(self, light_index: int) -> ShadowMapEntry | None:
        """Находит entry по индексу источника света."""
        for entry in self.entries:
            if entry.light_index == light_index:
                return entry
        return None
