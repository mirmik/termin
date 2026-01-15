from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from termin.graphics import RenderState

if TYPE_CHECKING:
    from termin._native.render import TcMaterial


@dataclass
class RenderPass:
    """
    Один проход рендеринга.

    Хранит TcMaterial напрямую.
    """
    _material: Optional["TcMaterial"] = field(default=None)
    state: RenderState = field(default_factory=RenderState)
    phase: str = "main"
    name: str = "unnamed_pass"

    @property
    def material(self) -> Optional["TcMaterial"]:
        """Возвращает материал."""
        return self._material

    @material.setter
    def material(self, value: Optional["TcMaterial"]):
        """Устанавливает материал."""
        self._material = value

    @classmethod
    def from_material(cls, material: "TcMaterial", state: RenderState | None = None) -> "RenderPass":
        """Создать RenderPass из материала."""
        return cls(
            _material=material,
            state=state or RenderState(),
        )

    @classmethod
    def from_material_name(cls, name: str, state: RenderState | None = None) -> "RenderPass":
        """Создать RenderPass по имени материала из ResourceManager."""
        from termin.assets.resources import ResourceManager

        rm = ResourceManager.instance()
        asset = rm.get_material_asset(name)
        material = asset.material if asset is not None else None
        return cls(
            _material=material,
            state=state or RenderState(),
        )