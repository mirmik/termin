"""AudioClipAsset and AudioClipHandle - Audio resource management."""

from __future__ import annotations

import ctypes
from pathlib import Path
from typing import TYPE_CHECKING

from termin.visualization.core.asset import Asset
from termin.visualization.core.resource_handle import ResourceHandle

if TYPE_CHECKING:
    pass


class AudioClipAsset(Asset):
    """
    Asset for audio files (.wav, .ogg, .mp3, .flac).

    IMPORTANT: Create through ResourceManager.get_or_create_audio_clip_asset(),
    not directly. This ensures proper registration and avoids duplicates.

    Stores Mix_Chunk (SDL_mixer loaded audio data).
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

        # Audio data (Mix_Chunk pointer from SDL_mixer)
        self._chunk: ctypes.c_void_p | None = None

        # Metadata (filled on load)
        self._duration_ms: int = 0

    @property
    def chunk(self) -> ctypes.c_void_p | None:
        """
        Get Mix_Chunk pointer (lazy loading).

        Returns:
            Mix_Chunk pointer or None if not loaded.
        """
        if not self._loaded:
            self.load()
        return self._chunk

    @property
    def duration_ms(self) -> int:
        """Duration in milliseconds (0 if unknown)."""
        return self._duration_ms

    @property
    def duration(self) -> float:
        """Duration in seconds (0.0 if unknown)."""
        return self._duration_ms / 1000.0

    def load(self) -> bool:
        """
        Load audio data from source_path.

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

        self._loaded = False

    def reload(self) -> bool:
        """Reload audio data from source_path."""
        self.unload()
        result = self.load()
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


class AudioClipHandle(ResourceHandle["ctypes.c_void_p", AudioClipAsset]):
    """
    Smart reference to audio clip.

    Usage:
        handle = AudioClipHandle.from_asset(asset)
        handle = AudioClipHandle.from_name("explosion")

        chunk = handle.get()  # Get Mix_Chunk pointer
        asset = handle.get_asset()  # Get AudioClipAsset
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
        from termin.visualization.core.resources import ResourceManager

        asset = ResourceManager.instance().get_audio_clip_asset(name)
        if asset is not None:
            return cls.from_asset(asset)
        return cls()

    @classmethod
    def from_uuid(cls, uuid: str) -> "AudioClipHandle":
        """Create handle by UUID (lookup in ResourceManager)."""
        from termin.visualization.core.resources import ResourceManager

        asset = ResourceManager.instance().get_audio_clip_asset_by_uuid(uuid)
        if asset is not None:
            return cls.from_asset(asset)
        return cls()

    def _get_resource_from_asset(self, asset: AudioClipAsset) -> "ctypes.c_void_p | None":
        """Extract Mix_Chunk from AudioClipAsset (lazy loading)."""
        return asset.chunk

    @property
    def chunk(self) -> "ctypes.c_void_p | None":
        """Get Mix_Chunk pointer."""
        return self.get()

    @property
    def duration(self) -> float:
        """Get duration in seconds."""
        if self._asset is not None:
            return self._asset.duration
        return 0.0

    @property
    def duration_ms(self) -> int:
        """Get duration in milliseconds."""
        if self._asset is not None:
            return self._asset.duration_ms
        return 0

    @property
    def is_loaded(self) -> bool:
        """Check if audio is loaded."""
        if self._asset is not None:
            return self._asset.is_loaded
        return False

    def ensure_loaded(self) -> bool:
        """Ensure audio is loaded. Returns True if successful."""
        if self._asset is not None:
            return self._asset.ensure_loaded()
        return False

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
