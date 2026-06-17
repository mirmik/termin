"""Smart reference to an AudioClip resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin_assets import ResourceHandle

if TYPE_CHECKING:
    from termin.audio.asset import AudioClipAsset
    from termin.audio.audio_clip import AudioClip


class AudioClipHandle(ResourceHandle["AudioClip", "AudioClipAsset"]):
    """Smart reference to AudioClip."""

    _asset_getter = "get_audio_clip_asset"
    _asset_by_uuid_getter = "get_audio_clip_asset_by_uuid"

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
