"""Serialization mixin for ResourceManager."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from termin.assets.texture_asset import TextureAsset


class SerializationMixin:
    """Mixin for serialization/deserialization."""

    def serialize(self) -> dict:
        """
        Сериализует все ресурсы ResourceManager.

        Материалы и меши не сериализуются — они загружаются из файлов проекта.
        """
        return {
            "textures": {name: self._serialize_texture_asset(asset) for name, asset in self._texture_assets.items()},
        }

    def _serialize_texture_asset(self, asset: "TextureAsset") -> dict:
        """Сериализует TextureAsset."""
        source_path = str(asset.source_path) if asset.source_path else None
        if source_path:
            return {"type": "file", "source_path": source_path}
        return {"type": "unknown"}

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "SerializationMixin":
        """
        Восстанавливает ресурсы из сериализованных данных в синглтон.

        Добавляет десериализованные ресурсы к существующему синглтону.
        Меши и материалы загружаются из файлов проекта, не из сцены.
        """
        return cls.instance()
