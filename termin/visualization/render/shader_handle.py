"""
ShaderHandle — умная ссылка на ShaderAsset.

Указывает на ShaderAsset напрямую или по имени через ResourceManager.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.core.resource_handle import ResourceHandle

if TYPE_CHECKING:
    from termin.visualization.render.shader_asset import ShaderAsset
    from termin.visualization.render.shader_parser import ShaderMultyPhaseProgramm


def _get_shader_asset(name: str) -> "ShaderAsset | None":
    """Lookup ShaderAsset by name in ResourceManager."""
    from termin.visualization.core.resources import ResourceManager

    return ResourceManager.instance().get_shader_asset(name)


class ShaderHandle(ResourceHandle["ShaderAsset"]):
    """
    Умная ссылка на ShaderAsset.

    Использование:
        handle = ShaderHandle.from_asset(asset)      # прямая ссылка на asset
        handle = ShaderHandle.from_program(prog)    # прямая ссылка (создаёт asset)
        handle = ShaderHandle.from_name("PBR")      # по имени (hot-reload)
    """

    _resource_getter = staticmethod(_get_shader_asset)

    @classmethod
    def from_asset(cls, asset: "ShaderAsset") -> "ShaderHandle":
        """Создать handle с прямой ссылкой на ShaderAsset."""
        handle = cls()
        handle._init_direct(asset)
        return handle

    @classmethod
    def from_program(cls, program: "ShaderMultyPhaseProgramm") -> "ShaderHandle":
        """
        Создать handle из ShaderMultyPhaseProgramm (обратная совместимость).

        Создаёт ShaderAsset из program.
        """
        from termin.visualization.render.shader_asset import ShaderAsset

        asset = ShaderAsset.from_program(program)
        return cls.from_asset(asset)

    @classmethod
    def from_name(cls, name: str) -> "ShaderHandle":
        """Создать handle по имени шейдера."""
        handle = cls()
        handle._init_named(name)
        return handle

    # --- Convenience accessors ---

    def get_asset(self) -> "ShaderAsset | None":
        """Получить ShaderAsset."""
        return self.get()

    @property
    def asset(self) -> "ShaderAsset | None":
        """Алиас для get()."""
        return self.get()

    def get_program(self) -> "ShaderMultyPhaseProgramm | None":
        """Получить ShaderMultyPhaseProgramm."""
        asset = self.get()
        if asset is not None:
            return asset.program
        return None

    # --- Serialization ---

    def serialize(self) -> dict:
        """Сериализация."""
        if self._direct is not None:
            if self._direct.source_path:
                return {
                    "type": "path",
                    "path": str(self._direct.source_path),
                }
            return {
                "type": "named",
                "name": self._direct.name,
            }
        elif self._name is not None:
            return {
                "type": "named",
                "name": self._name,
            }
        else:
            return {"type": "none"}

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

        return cls()
