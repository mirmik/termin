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
class ClearSpec:
    """
    Спецификация очистки ресурса перед рендерингом.
    
    resource: имя ресурса (FBO)
    color: RGBA цвет очистки (None — не очищать цвет)
    depth: значение глубины (None — не очищать глубину)
    """
    resource: str
    color: Tuple[float, float, float, float] | None = (0.0, 0.0, 0.0, 1.0)
    depth: float | None = 1.0


@dataclass
class RenderPipeline:
    """
    Контейнер конвейера рендеринга.
    
    passes: список FramePass
    clear_specs: список ClearSpec для очистки ресурсов перед рендерингом
    debug_blit_pass: ссылка на BlitPass для управления из дебаггера (опционально)
    """
    passes: List["FramePass"] = field(default_factory=list)
    clear_specs: List[ClearSpec] = field(default_factory=list)
    debug_blit_pass: "BlitPass | None" = None
