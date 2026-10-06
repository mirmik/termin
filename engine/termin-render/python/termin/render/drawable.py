"""
Drawable protocol.

Runtime passes collect RenderItems through the native drawable protocol.

Разделение ответственности:
- FramePass отвечает за привязку шейдера/материала
- Drawable/renderer submits RenderItems
- RenderItem encoders own backend-specific draw details
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from termin.materials import TcMaterial
    from termin.render._render_native import RenderCamera
    from termin.scene import TcScene

from termin.render._render_native import (
    RENDER_ITEM_COLLECT_ALLOW_MISSING_MATERIAL_PHASE,
    RenderItem,
)


# Идентификатор геометрии по умолчанию
DEFAULT_GEOMETRY_ID = 0


@dataclass(frozen=True)
class RenderItemCollectContext:
    phase: int = 0
    flags: int = 0
    layer_mask: int = (1 << 64) - 1
    render_category_mask: int = (1 << 64) - 1
    debug_pass_name: str = ""
    camera: RenderCamera | None = None
    scene: TcScene | None = None

    @property
    def allow_missing_material_phase(self) -> bool:
        return (self.flags & RENDER_ITEM_COLLECT_ALLOW_MISSING_MATERIAL_PHASE) != 0


@runtime_checkable
class Drawable(Protocol):
    """
    Protocol for components that submit renderable work through RenderItems.

    Атрибуты:
        phase_mask: Битовая маска фаз, в которых участвует drawable.

    Методы:
        collect_render_items: Возвращает RenderItems для указанного pass context.
                              Нулевая phase означает pass-neutral snapshot
                              и требует вернуть все phase-варианты за один вызов.
    """

    phase_mask: int

    def collect_materials(self, context: RenderItemCollectContext) -> Iterable[TcMaterial]:
        """Return only materials selected for rendering in the same context.

        This mandatory lightweight callback must not construct RenderItems or
        geometry. Return an empty iterable explicitly when no material is used.
        """
        ...

    def collect_render_items(self, context: RenderItemCollectContext) -> list[RenderItem]:
        """
        Возвращает RenderItems для текущей фазы pass-а или все варианты для
        snapshot collection при нулевой phase.
        """
        ...


__all__ = [
    "DEFAULT_GEOMETRY_ID",
    "Drawable",
    "RenderItem",
    "RenderItemCollectContext",
]
