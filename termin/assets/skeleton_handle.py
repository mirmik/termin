"""
SkeletonHandle — умная ссылка на скелет.

Два режима:
1. Direct — хранит SkeletonData напрямую
2. Asset — хранит SkeletonAsset (lookup по имени через ResourceManager)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.assets.resource_handle import ResourceHandle

if TYPE_CHECKING:
    from termin.skeleton import SkeletonData
    from termin.assets.skeleton_asset import SkeletonAsset


class SkeletonHandle(ResourceHandle["SkeletonData", "SkeletonAsset"]):
    """
    Умная ссылка на скелет.

    Использование:
        handle = SkeletonHandle.from_direct(skeleton)  # raw SkeletonData
        handle = SkeletonHandle.from_asset(asset)      # SkeletonAsset
        handle = SkeletonHandle.from_name("humanoid")  # lookup в ResourceManager
    """

    _asset_getter = "get_skeleton_asset"

    @classmethod
    def from_direct(cls, skeleton: "SkeletonData") -> "SkeletonHandle":
        """Создать handle с raw SkeletonData."""
        handle = cls()
        handle._init_direct(skeleton)
        return handle

    # Alias for backward compatibility
    from_skeleton = from_direct

    # --- Convenience accessors ---

    @property
    def skeleton(self) -> "SkeletonData | None":
        """Получить SkeletonData."""
        return self.get()

    @property
    def asset(self) -> "SkeletonAsset | None":
        """Получить SkeletonAsset."""
        return self.get_asset()

    def get_skeleton(self) -> "SkeletonData | None":
        """Получить SkeletonData."""
        return self.get()

    def get_skeleton_or_none(self) -> "SkeletonData | None":
        """Алиас для get_skeleton()."""
        return self.get()

    # --- Serialization ---

    def _serialize_direct(self) -> dict:
        """Сериализовать raw SkeletonData."""
        return {"type": "direct_unsupported"}

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "SkeletonHandle":
        """Десериализация."""
        handle_type = data.get("type", "none")

        if handle_type in ("named", "direct"):
            name = data.get("name")
            if name:
                return cls.from_name(name)

        return cls()
