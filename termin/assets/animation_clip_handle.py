"""
AnimationClipHandle — умная ссылка на анимационный клип.

Два режима:
1. Direct — хранит AnimationClip напрямую
2. Asset — хранит AnimationClipAsset (lookup по имени через ResourceManager)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.assets.resource_handle import ResourceHandle

if TYPE_CHECKING:
    from termin.visualization.animation.clip import AnimationClip
    from termin.visualization.animation.animation_clip_asset import AnimationClipAsset


class AnimationClipHandle(ResourceHandle["AnimationClip", "AnimationClipAsset"]):
    """
    Умная ссылка на анимационный клип.

    Использование:
        handle = AnimationClipHandle.from_direct(clip)  # raw AnimationClip
        handle = AnimationClipHandle.from_asset(asset)  # AnimationClipAsset
        handle = AnimationClipHandle.from_name("walk")  # lookup в ResourceManager
    """

    _asset_getter = "get_animation_clip_asset"

    @classmethod
    def from_direct(cls, clip: "AnimationClip") -> "AnimationClipHandle":
        """Создать handle с raw AnimationClip."""
        handle = cls()
        handle._init_direct(clip)
        return handle

    # Alias for backward compatibility
    from_clip = from_direct

    @classmethod
    def from_uuid(cls, uuid: str) -> "AnimationClipHandle":
        """Создать handle по UUID (lookup в ResourceManager)."""
        from termin.assets.resources import ResourceManager

        asset = ResourceManager.instance().get_animation_clip_asset_by_uuid(uuid)
        if asset is not None:
            return cls.from_asset(asset)
        return cls()

    # --- Convenience accessors ---

    @property
    def clip(self) -> "AnimationClip | None":
        """Получить AnimationClip."""
        return self.get()

    @property
    def asset(self) -> "AnimationClipAsset | None":
        """Получить AnimationClipAsset."""
        return self.get_asset()

    def get_clip(self) -> "AnimationClip | None":
        """Получить AnimationClip."""
        return self.get()

    def get_clip_or_none(self) -> "AnimationClip | None":
        """Алиас для get_clip()."""
        return self.get()

    # --- Serialization ---

    def _serialize_direct(self) -> dict:
        """Сериализовать raw AnimationClip."""
        return {"type": "direct_unsupported"}

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "AnimationClipHandle":
        """Десериализация."""
        handle_type = data.get("type", "none")

        if handle_type in ("named", "direct"):
            name = data.get("name")
            if name:
                return cls.from_name(name)

        return cls()


__all__ = ["AnimationClipHandle"]
