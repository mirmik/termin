"""Serialization mixin for default resource managers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from termin.default_assets.render.texture_asset import TextureAsset


class DefaultSerializationMixin:
    """Serialize runtime resource-manager state that is not file-backed."""

    def serialize(self) -> dict:
        return {
            "textures": {name: self._serialize_texture_asset(asset) for name, asset in self._texture_assets.items()},
        }

    def _serialize_texture_asset(self, asset: "TextureAsset") -> dict:
        source_path = str(asset.source_path) if asset.source_path else None
        if source_path:
            return {"type": "file", "source_path": source_path}
        return {"type": "unknown"}

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "DefaultSerializationMixin":
        return cls.instance()
