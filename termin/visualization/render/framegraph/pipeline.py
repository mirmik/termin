"""
RenderPipeline — контейнер для конвейера рендеринга.

Содержит:
- passes: список FramePass, определяющих порядок рендеринга
- clear_resources: список ресурсов (FBO), которые нужно очистить перед стартом

Также хранит ссылку на DebugBlitPass, чтобы дебаггер мог
напрямую управлять его состоянием (reads, enabled).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from termin.visualization.render.framegraph.core import FramePass
    from termin.visualization.render.framegraph.passes.present import BlitPass


@dataclass
class ResourceSpec:
    """
    Спецификация требований к ресурсу (FBO).

    Объединяет различные требования pass'а к ресурсу:
    - Размер (например, для shadow map - фиксированный 1024x1024)
    - Очистка (цвет и/или глубина)
    - Формат (для будущего: depth texture, RGBA16F, и т.д.)

    Атрибуты:
        resource: имя ресурса (FBO)
        size: требуемый размер (width, height) или None для размера viewport'а
        clear_color: RGBA цвет очистки (None — не очищать цвет)
        clear_depth: значение глубины (None — не очищать глубину)
        format: формат текстуры/attachment'ов (None — по умолчанию)
    """
    resource: str
    size: Tuple[int, int] | None = None
    clear_color: Tuple[float, float, float, float] | None = None
    clear_depth: float | None = None
    format: str | None = None


@dataclass
class RenderPipeline:
    """
    Контейнер конвейера рендеринга.

    passes: список FramePass
    debug_blit_pass: ссылка на BlitPass для управления из дебаггера (опционально)

    Спецификации ресурсов (размер, очистка, формат) теперь объявляются
    самими pass'ами через метод get_resource_specs().
    """
    passes: List["FramePass"] = field(default_factory=list)
    debug_blit_pass: "BlitPass | None" = None
