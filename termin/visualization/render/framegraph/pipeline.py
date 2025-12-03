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
from typing import TYPE_CHECKING, List

from termin.visualization.render.framegraph.resource_spec import ResourceSpec

if TYPE_CHECKING:
    from termin.visualization.render.framegraph.core import FramePass
    from termin.visualization.render.framegraph.passes.present import BlitPass


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
    pipeline_specs: List[ResourceSpec] = field(default_factory=list)
