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
