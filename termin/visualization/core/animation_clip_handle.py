"""
AnimationClipHandle — умная ссылка на AnimationClipAsset.

Указывает на AnimationClipAsset напрямую или по имени через ResourceManager.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.core.resource_handle import ResourceHandle

if TYPE_CHECKING:
    from termin.visualization.animation.clip import AnimationClip
    from termin.visualization.animation.animation_clip_asset import AnimationClipAsset


def _get_animation_clip_asset(name: str) -> "AnimationClipAsset | None":
    """Lookup AnimationClipAsset by name in ResourceManager."""
    from termin.visualization.core.resources import ResourceManager

    return ResourceManager.instance().get_animation_clip_asset(name)


class AnimationClipHandle(ResourceHandle["AnimationClipAsset"]):
    """
    Умная ссылка на AnimationClipAsset.

    Использование:
        handle = AnimationClipHandle.from_asset(asset)  # прямая ссылка на asset
        handle = AnimationClipHandle.from_clip(clip)    # прямая ссылка (создаёт asset)
        handle = AnimationClipHandle.from_name("walk")  # по имени (hot-reload)
    """

    _resource_getter = staticmethod(_get_animation_clip_asset)

    @classmethod
    def from_asset(cls, asset: "AnimationClipAsset") -> "AnimationClipHandle":
        """Создать handle с прямой ссылкой на AnimationClipAsset."""
        handle = cls()
        handle._init_direct(asset)
        return handle

    @classmethod
    def from_clip(cls, clip: "AnimationClip") -> "AnimationClipHandle":
        """
        Создать handle из AnimationClip (обратная совместимость).

        Создаёт AnimationClipAsset из AnimationClip.
        """
        from termin.visualization.animation.animation_clip_asset import AnimationClipAsset

        asset = AnimationClipAsset.from_clip(clip)
        return cls.from_asset(asset)

    @classmethod
    def from_name(cls, name: str) -> "AnimationClipHandle":
        """Создать handle по имени AnimationClip."""
        handle = cls()
        handle._init_named(name)
        return handle

    # --- Convenience accessors ---

    def get_asset(self) -> "AnimationClipAsset | None":
        """Получить AnimationClipAsset."""
        return self.get()

    @property
    def asset(self) -> "AnimationClipAsset | None":
        """Алиас для get()."""
        return self.get()

    def get_clip(self) -> "AnimationClip | None":
        """
        Получить AnimationClip.

        Returns:
            AnimationClip или None если недоступен
        """
        asset = self.get()
        if asset is not None:
            return asset.clip
        return None

    def get_clip_or_none(self) -> "AnimationClip | None":
        """Алиас для get_clip()."""
        return self.get_clip()

    # --- Serialization ---

    def serialize(self) -> dict:
        """Сериализация."""
        if self._direct is not None:
            return {
                "type": "direct",
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
    def deserialize(cls, data: dict, context=None) -> "AnimationClipHandle":
        """Десериализация."""
        handle_type = data.get("type", "none")

        if handle_type == "named":
            name = data.get("name")
            if name:
                return cls.from_name(name)
        elif handle_type == "direct":
            name = data.get("name")
            if name:
                return cls.from_name(name)

        return cls()


__all__ = ["AnimationClipHandle"]
