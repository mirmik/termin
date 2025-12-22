from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass
class ResourceSpec:
    """
    Спецификация требований к ресурсу конвейера.

    Объединяет различные требования pass'а к ресурсу:
    - Тип ресурса (FBO, ShadowMapArray, и т.д.)
    - Размер (например, для shadow map — фиксированный 1024x1024)
    - Очистка (цвет и/или глубина)
    - Формат (для будущего: depth texture, RGBA16F и т.д.)

    Атрибуты:
        resource: имя ресурса
        resource_type: тип ресурса:
            - "fbo" (по умолчанию) — стандартный framebuffer
            - "shadow_map_array" — массив shadow maps (ShadowMapArray)
        size: требуемый размер (width, height) или None для размера viewport'а
        clear_color: RGBA цвет очистки (None — не очищать цвет)
        clear_depth: значение глубины (None — не очищать глубину)
        format: формат текстуры/attachment'ов (None — по умолчанию)
    
    Если спек для ресурса не объявлен, считается что это FBO 
    с размером viewport'а камеры (обратная совместимость).
    """

    resource: str
    resource_type: str = "fbo"
    size: Tuple[int, int] | None = None
    clear_color: Tuple[float, float, float, float] | None = None
    clear_depth: float | None = None
    format: str | None = None
    samples: int = 1  # 1 = без MSAA, 4 = 4x MSAA

    def serialize(self) -> dict:
        """Сериализует ResourceSpec в словарь."""
        data = {
            "resource": self.resource,
            "resource_type": self.resource_type,
        }
        if self.size is not None:
            data["size"] = list(self.size)
        if self.clear_color is not None:
            data["clear_color"] = list(self.clear_color)
        if self.clear_depth is not None:
            data["clear_depth"] = self.clear_depth
        if self.format is not None:
            data["format"] = self.format
        if self.samples != 1:
            data["samples"] = self.samples
        return data

    @classmethod
    def deserialize(cls, data: dict) -> "ResourceSpec":
        """Десериализует ResourceSpec из словаря."""
        size = None
        if "size" in data:
            size = tuple(data["size"])

        clear_color = None
        if "clear_color" in data:
            clear_color = tuple(data["clear_color"])

        return cls(
            resource=data.get("resource", ""),
            resource_type=data.get("resource_type", "fbo"),
            size=size,
            clear_color=clear_color,
            clear_depth=data.get("clear_depth"),
            format=data.get("format"),
            samples=data.get("samples", 1),
        )
