"""
ShaderHandle — умная ссылка на шейдер.

Два режима:
1. Direct — хранит ShaderMultyPhaseProgramm напрямую
2. Asset — хранит ShaderAsset (lookup по имени через ResourceManager)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.assets.resource_handle import ResourceHandle

if TYPE_CHECKING:
    from termin.visualization.render.shader_asset import ShaderAsset
    from termin.visualization.render.shader_parser import ShaderMultyPhaseProgramm


class ShaderHandle(ResourceHandle["ShaderMultyPhaseProgramm", "ShaderAsset"]):
    """
    Умная ссылка на шейдер.

    Использование:
        handle = ShaderHandle.from_direct(program)   # raw ShaderMultyPhaseProgramm
        handle = ShaderHandle.from_asset(asset)      # ShaderAsset
        handle = ShaderHandle.from_name("PBR")       # lookup в ResourceManager
    """

    _asset_getter = "get_shader_asset"

    @classmethod
    def from_direct(cls, program: "ShaderMultyPhaseProgramm") -> "ShaderHandle":
        """Создать handle с raw ShaderMultyPhaseProgramm."""
        handle = cls()
        handle._init_direct(program)
        return handle

    # --- Convenience accessors ---

    @property
    def program(self) -> "ShaderMultyPhaseProgramm | None":
        """Получить ShaderMultyPhaseProgramm."""
        return self.get()

    @property
    def asset(self) -> "ShaderAsset | None":
        """Получить ShaderAsset."""
        return self.get_asset()

    # --- Serialization ---

    def _serialize_direct(self) -> dict:
        """Сериализовать raw ShaderMultyPhaseProgramm."""
        if self._direct is not None:
            return self._direct.direct_serialize()
        return {"type": "direct_unsupported"}

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "ShaderHandle":
        """Десериализация."""
        from termin.visualization.render.shader_asset import ShaderAsset

        handle_type = data.get("type", "none")

        if handle_type == "named":
            name = data.get("name")
            if name:
                return cls.from_name(name)
        elif handle_type == "path":
            path = data.get("path")
            if path:
                asset = ShaderAsset.from_file(path)
                return cls.from_asset(asset)
        # TODO: handle "inline" type for raw program deserialization

        return cls()
