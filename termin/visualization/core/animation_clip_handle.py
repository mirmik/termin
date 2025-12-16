# termin/visualization/core/animation_clip_handle.py
"""
AnimationClipKeeper and AnimationClipHandle - animation clip resource management.

Inherits from ResourceKeeper/ResourceHandle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.core.resource_handle import ResourceHandle, ResourceKeeper

if TYPE_CHECKING:
    from termin.visualization.animation.clip import AnimationClip


class AnimationClipKeeper(ResourceKeeper["AnimationClip"]):
    """
    Owner of AnimationClip by name.

    AnimationClip does not require GPU cleanup.
    """

    @property
    def clip(self) -> "AnimationClip | None":
        """Alias for resource."""
        return self._resource

    @property
    def has_clip(self) -> bool:
        """Alias for has_resource."""
        return self.has_resource

    def set_clip(self, clip: "AnimationClip", source_path: str | None = None) -> None:
        """Alias for set_resource."""
        self.set_resource(clip, source_path)

    def update_clip(self, clip: "AnimationClip") -> None:
        """Alias for update_resource."""
        self.update_resource(clip)

    def _on_cleanup(self, resource: "AnimationClip") -> None:
        """AnimationClip does not require special cleanup."""
        pass


class AnimationClipHandle(ResourceHandle["AnimationClip"]):
    """
    Smart reference to AnimationClip.

    Usage:
        handle = AnimationClipHandle.from_clip(clip)  # direct reference
        handle = AnimationClipHandle.from_name("walk_cycle")  # by name (hot-reload)
    """

    @classmethod
    def from_clip(cls, clip: "AnimationClip") -> "AnimationClipHandle":
        """Create handle with direct reference to AnimationClip."""
        handle = cls()
        handle._init_direct(clip)
        return handle

    @classmethod
    def from_name(cls, name: str) -> "AnimationClipHandle":
        """Create handle by AnimationClip name."""
        from termin.visualization.core.resources import ResourceManager

        handle = cls()
        keeper = ResourceManager.instance().get_or_create_animation_clip_keeper(name)
        handle._init_named(name, keeper)
        return handle

    def serialize(self) -> dict:
        """Serialization."""
        if self._direct is not None:
            return {
                "type": "direct",
                "name": self._direct.name if hasattr(self._direct, "name") else None,
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
        """Deserialization."""
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


__all__ = ["AnimationClipKeeper", "AnimationClipHandle"]
