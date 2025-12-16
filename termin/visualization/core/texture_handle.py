"""
TextureHandle — умная ссылка на TextureAsset.

Указывает на TextureAsset напрямую или по имени через ResourceManager.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.core.resource_handle import ResourceHandle

if TYPE_CHECKING:
    from termin.visualization.render.texture import Texture
    from termin.visualization.render.texture_asset import TextureAsset


def _get_texture_asset(name: str) -> "TextureAsset | None":
    """Lookup TextureAsset by name in ResourceManager."""
    from termin.visualization.core.resources import ResourceManager

    return ResourceManager.instance().get_texture_asset(name)


class TextureHandle(ResourceHandle["TextureAsset"]):
    """
    Умная ссылка на TextureAsset.

    Использование:
        handle = TextureHandle.from_asset(asset)   # прямая ссылка
        handle = TextureHandle.from_name("wood")   # по имени (hot-reload)
    """

    _resource_getter = staticmethod(_get_texture_asset)

    @classmethod
    def from_asset(cls, asset: "TextureAsset") -> "TextureHandle":
        """Создать handle с прямой ссылкой на TextureAsset."""
        handle = cls()
        handle._init_direct(asset)
        return handle

    @classmethod
    def from_texture(cls, texture: "Texture") -> "TextureHandle":
        """
        Создать handle из Texture (обратная совместимость).

        Извлекает TextureAsset из Texture.
        """
        from termin.visualization.render.texture import Texture

        if isinstance(texture, Texture):
            asset = texture.asset
            if asset is not None:
                return cls.from_asset(asset)
        return cls()

    @classmethod
    def from_name(cls, name: str) -> "TextureHandle":
        """Создать handle по имени текстуры."""
        handle = cls()
        handle._init_named(name)
        return handle

    # --- Convenience accessors ---

    def get_asset(self) -> "TextureAsset | None":
        """Получить TextureAsset."""
        return self.get()

    @property
    def asset(self) -> "TextureAsset | None":
        """Алиас для get()."""
        return self.get()

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
    def deserialize(cls, data: dict, context=None) -> "TextureHandle":
        """Десериализация."""
        from termin.visualization.render.texture_asset import TextureAsset

        handle_type = data.get("type", "none")

        if handle_type == "named":
            name = data.get("name")
            if name:
                return cls.from_name(name)
        elif handle_type == "path":
            path = data.get("path")
            if path:
                asset = TextureAsset.from_file(path)
                return cls.from_asset(asset)

        return cls()
