"""AudioClipHandle - smart reference to AudioClip."""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.assets.resource_handle import ResourceHandle

if TYPE_CHECKING:
    from termin.audio.audio_clip import AudioClip
    from termin.assets.audio_clip_asset import AudioClipAsset


class AudioClipHandle(ResourceHandle["AudioClip", "AudioClipAsset"]):
    """
    Smart reference to AudioClip.

    Usage:
        handle = AudioClipHandle.from_asset(asset)
        handle = AudioClipHandle.from_name("explosion")

        clip = handle.get()  # Get AudioClip
        clip = handle.clip   # Same, via property
    """

    @classmethod
    def from_asset(cls, asset: "AudioClipAsset") -> "AudioClipHandle":
        """Create handle from AudioClipAsset."""
        handle = cls()
        handle._init_asset(asset)
        return handle

    @classmethod
    def from_name(cls, name: str) -> "AudioClipHandle":
        """Create handle by name (lookup in ResourceManager)."""
        from termin.assets.resources import ResourceManager

        asset = ResourceManager.instance().get_audio_clip_asset(name)
        if asset is not None:
            return cls.from_asset(asset)
        return cls()

    @classmethod
    def from_uuid(cls, uuid: str) -> "AudioClipHandle":
        """Create handle by UUID (lookup in ResourceManager)."""
        from termin.assets.resources import ResourceManager

        asset = ResourceManager.instance().get_audio_clip_asset_by_uuid(uuid)
        if asset is not None:
            return cls.from_asset(asset)
        return cls()

    def _get_resource_from_asset(self, asset: "AudioClipAsset") -> "AudioClip | None":
        """Extract AudioClip from AudioClipAsset (lazy loading)."""
        return asset.clip

    @property
    def clip(self) -> "AudioClip | None":
        """Get AudioClip."""
        return self.get()

    @property
    def duration(self) -> float:
        """Get duration in seconds."""
        clip = self.get()
        if clip is not None:
            return clip.duration
        return 0.0

    @property
    def duration_ms(self) -> int:
        """Get duration in milliseconds."""
        clip = self.get()
        if clip is not None:
            return clip.duration_ms
        return 0

    @property
    def is_valid(self) -> bool:
        """Check if handle points to valid audio."""
        clip = self.get()
        return clip is not None and clip.is_valid

    # --- Serialization ---

    def serialize(self) -> dict:
        """Serialize for scene saving."""
        if self._asset is not None:
            return {
                "type": "uuid",
                "uuid": self._asset.uuid,
            }
        return {"type": "none"}

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "AudioClipHandle":
        """Deserialize from saved data."""
        handle_type = data.get("type", "none")

        if handle_type == "uuid":
            uuid = data.get("uuid")
            if uuid:
                return cls.from_uuid(uuid)
        elif handle_type == "name":
            name = data.get("name")
            if name:
                return cls.from_name(name)

        return cls()
