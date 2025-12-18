"""
TextureHandle — умная ссылка на текстуру.

Два режима:
1. Direct — хранит TextureData напрямую
2. Asset — хранит TextureAsset (lookup по имени через ResourceManager)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.core.resource_handle import ResourceHandle

if TYPE_CHECKING:
    from termin.visualization.render.texture_data import TextureData
    from termin.visualization.render.texture_asset import TextureAsset


class TextureHandle(ResourceHandle["TextureData", "TextureAsset"]):
    """
    Умная ссылка на текстуру.

    Использование:
        handle = TextureHandle.from_direct(texture_data)  # raw TextureData
        handle = TextureHandle.from_asset(asset)          # TextureAsset
        handle = TextureHandle.from_name("wood")          # lookup в ResourceManager
    """

    @classmethod
    def from_direct(cls, texture_data: "TextureData") -> "TextureHandle":
        """Создать handle с raw TextureData."""
        handle = cls()
        handle._init_direct(texture_data)
        return handle

    @classmethod
    def from_asset(cls, asset: "TextureAsset") -> "TextureHandle":
        """Создать handle с TextureAsset."""
        handle = cls()
        handle._init_asset(asset)
        return handle

    @classmethod
    def from_name(cls, name: str) -> "TextureHandle":
        """Создать handle по имени (lookup в ResourceManager)."""
        from termin.visualization.core.resources import ResourceManager

        asset = ResourceManager.instance().get_texture_asset(name)
        if asset is not None:
            return cls.from_asset(asset)
        return cls()

    # --- Resource extraction ---

    def _get_resource_from_asset(self, asset: "TextureAsset") -> "TextureData | None":
        """Извлечь TextureData из TextureAsset (lazy loading)."""
        if not asset.is_loaded:
            asset.load()
        return asset.texture_data

    # --- Convenience accessors ---

    @property
    def texture_data(self) -> "TextureData | None":
        """Получить TextureData."""
        return self.get()

    @property
    def asset(self) -> "TextureAsset | None":
        """Получить TextureAsset."""
        return self.get_asset()

    def get_texture_data(self) -> "TextureData | None":
        """Получить TextureData."""
        return self.get()

    # --- Serialization ---

    def _serialize_direct(self) -> dict:
        """Сериализовать raw TextureData."""
        if self._direct is not None:
            return self._direct.direct_serialize()
        return {"type": "direct_unsupported"}

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
