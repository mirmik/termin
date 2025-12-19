"""AudioClip, AudioClipAsset and AudioClipHandle - Audio resource management."""

from __future__ import annotations

import ctypes
from pathlib import Path
from typing import TYPE_CHECKING

from termin.assets.asset import Asset
from termin.assets.resource_handle import ResourceHandle

if TYPE_CHECKING:
    pass


class AudioClip:
    """
    Audio clip data - wrapper around SDL_mixer Mix_Chunk.

    This is the actual audio resource that components work with.
    Does not know about UUIDs, file paths, or asset management.
    """

    def __init__(self, chunk: ctypes.c_void_p, duration_ms: int = 0):
        """
        Initialize AudioClip.

        Args:
            chunk: Mix_Chunk pointer from SDL_mixer
            duration_ms: Duration in milliseconds (0 if unknown)
        """
        self._chunk: ctypes.c_void_p = chunk
        self._duration_ms: int = duration_ms

    @property
    def chunk(self) -> ctypes.c_void_p:
        """Get Mix_Chunk pointer for SDL_mixer operations."""
        return self._chunk

    @property
    def duration_ms(self) -> int:
        """Duration in milliseconds."""
        return self._duration_ms

    @property
    def duration(self) -> float:
        """Duration in seconds."""
        return self._duration_ms / 1000.0

    @property
    def is_valid(self) -> bool:
        """Check if clip has valid audio data."""
        return self._chunk is not None


class AudioClipAsset(Asset):
    """
    Asset for audio files (.wav, .ogg, .mp3, .flac).

    IMPORTANT: Create through ResourceManager.get_or_create_audio_clip_asset(),
    not directly. This ensures proper registration and avoids duplicates.

    Loads audio file and creates AudioClip on demand.
    Supports lazy loading - audio is loaded on first access.
    """

    # Supported audio file extensions
    SUPPORTED_EXTENSIONS = {".wav", ".ogg", ".mp3", ".flac"}

    def __init__(
        self,
        name: str = "audio_clip",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        """
        Initialize AudioClipAsset.

        Args:
            name: Human-readable name
            source_path: Path to audio file
            uuid: Existing UUID or None to generate new one
        """
        super().__init__(name=name, source_path=source_path, uuid=uuid)

        # The actual audio clip (created on load)
        self._clip: AudioClip | None = None

        # Raw chunk pointer for cleanup
        self._chunk: ctypes.c_void_p | None = None

    @property
    def clip(self) -> AudioClip | None:
        """
        Get AudioClip (lazy loading).

        Returns:
            AudioClip or None if not loaded.
        """
        if not self._loaded:
            self._load()
        return self._clip

    def _load(self) -> bool:
        """
        Load audio data from source_path (internal).

        Returns:
            True if loaded successfully.
        """
        if self._loaded:
            return True

        if self._source_path is None:
            return False

        from termin.audio.audio_engine import AudioEngine

        engine = AudioEngine.instance()
        chunk = engine.load_chunk(str(self._source_path))

        if chunk is None:
            return False

        self._chunk = chunk
        self._clip = AudioClip(chunk, duration_ms=0)
        self._loaded = True
        self._bump_version()

        print(f"[AudioClipAsset] Loaded: {self._name}")
        return True

    def unload(self) -> None:
        """Unload audio data to free memory."""
        if self._chunk is not None:
            from termin.audio.audio_engine import AudioEngine

            engine = AudioEngine.instance()
            engine.free_chunk(self._chunk)
            self._chunk = None

        self._clip = None
        self._loaded = False

    def reload(self) -> bool:
        """Reload audio data from source_path."""
        self.unload()
        result = self._load()
        if result:
            self._bump_version()
        return result

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        name: str | None = None,
        uuid: str | None = None,
    ) -> "AudioClipAsset":
        """
        Create AudioClipAsset from file path.

        Args:
            path: Path to audio file
            name: Optional name (defaults to filename without extension)
            uuid: Optional UUID

        Returns:
            AudioClipAsset instance (not yet loaded).
        """
        path = Path(path)
        if name is None:
            name = path.stem

        return cls(name=name, source_path=path, uuid=uuid)

    def __del__(self):
        """Ensure audio data is freed on garbage collection."""
        self.unload()


class AudioClipHandle(ResourceHandle[AudioClip, AudioClipAsset]):
    """
    Smart reference to AudioClip.

    Usage:
        handle = AudioClipHandle.from_asset(asset)
        handle = AudioClipHandle.from_name("explosion")

        clip = handle.get()  # Get AudioClip
        clip = handle.clip   # Same, via property
    """

    @classmethod
    def from_asset(cls, asset: AudioClipAsset) -> "AudioClipHandle":
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

    def _get_resource_from_asset(self, asset: AudioClipAsset) -> AudioClip | None:
        """Extract AudioClip from AudioClipAsset (lazy loading)."""
        return asset.clip

    @property
    def clip(self) -> AudioClip | None:
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
