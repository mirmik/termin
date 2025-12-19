"""AudioClipAsset - Asset for audio files.

NOTE: This class inherits from Asset directly, not DataAsset[AudioClip].
This is intentional due to how SDL_mixer works:

Standard DataAsset pattern:
    1. DataAsset reads file bytes
    2. _parse_content(bytes) parses bytes into data object

AudioClipAsset difference:
    SDL_mixer's Mix_LoadWAV() reads files directly by path.
    We cannot pass raw bytes to it.

Potential fix path:
    1. Add AudioEngine.load_chunk_from_bytes(data: bytes) using Mix_LoadWAV_RW
       with SDL_RWops created from memory buffer
    2. Refactor AudioClipAsset to inherit from DataAsset[AudioClip]
    3. Implement _parse_content() to call load_chunk_from_bytes()

For now, we accept this architectural difference.
"""

from __future__ import annotations

import ctypes
from pathlib import Path
from typing import TYPE_CHECKING

from termin.assets.asset import Asset

if TYPE_CHECKING:
    from termin.audio.audio_clip import AudioClip


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
        self._clip: "AudioClip | None" = None

        # Raw chunk pointer for cleanup
        self._chunk: ctypes.c_void_p | None = None

    @property
    def clip(self) -> "AudioClip | None":
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

        from termin.audio.audio_clip import AudioClip
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
