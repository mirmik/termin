from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from termin.visualization.core.material import Material


@dataclass
class RenderState:
    """
    Полное состояние, никаких "None".
    Это "каким хочешь видеть рендер сейчас".
    """
    polygon_mode: str = "fill"     # fill / line
    cull: bool = True
    depth_test: bool = True
    depth_write: bool = True
    blend: bool = False
    blend_src: str = "src_alpha"
    blend_dst: str = "one_minus_src_alpha"


@dataclass
class RenderPass:
    """
    Один проход рендеринга.

    Хранит MaterialHandle вместо Material напрямую.
    При доступе к material возвращает актуальный материал через handle.
    """
    _material_handle: "MaterialHandle" = field(default=None)  # type: ignore
    state: RenderState = field(default_factory=RenderState)
    phase: str = "main"
    name: str = "unnamed_pass"

    def __post_init__(self):
        from termin.visualization.core.material_handle import MaterialHandle

        # Если передали None — создаём пустой handle
        if self._material_handle is None:
            self._material_handle = MaterialHandle()

    @property
    def material(self) -> "Material":
        """Возвращает актуальный материал через handle."""
        return self._material_handle.get()

    @material.setter
    def material(self, value: "Material | None"):
        """Устанавливает материал (создаёт direct handle)."""
        from termin.visualization.core.material_handle import MaterialHandle

        if value is None:
            self._material_handle = MaterialHandle()
        else:
            self._material_handle = MaterialHandle.from_material(value)

    @property
    def material_handle(self) -> "MaterialHandle":
        """Доступ к handle напрямую."""
        return self._material_handle

    @material_handle.setter
    def material_handle(self, value: "MaterialHandle"):
        """Установить handle напрямую."""
        self._material_handle = value

    @classmethod
    def from_material(cls, material: "Material", state: RenderState | None = None) -> "RenderPass":
        """Создать RenderPass из материала."""
        from termin.visualization.core.material_handle import MaterialHandle

        handle = MaterialHandle.from_material(material)
        return cls(
            _material_handle=handle,
            state=state or RenderState(),
        )

    @classmethod
    def from_material_name(cls, name: str, state: RenderState | None = None) -> "RenderPass":
        """Создать RenderPass по имени материала из ResourceManager."""
        from termin.visualization.core.material_handle import MaterialHandle

        handle = MaterialHandle.from_name(name)
        return cls(
            _material_handle=handle,
            state=state or RenderState(),
        )


# Для обратной совместимости импорта
from termin.visualization.core.material_handle import MaterialHandle