"""Audio clip asset model."""

from __future__ import annotations

import ctypes
from pathlib import Path
from typing import TYPE_CHECKING

from tcbase import log
from termin_assets import Asset

if TYPE_CHECKING:
    from termin.audio.audio_clip import AudioClip


class AudioClipAsset(Asset):
    """
    Asset for audio files (.wav, .ogg, .mp3, .flac).

    SDL_mixer currently loads files directly by path, so this class inherits
    from Asset directly instead of DataAsset[AudioClip].
    """

    SUPPORTED_EXTENSIONS = {".wav", ".ogg", ".mp3", ".flac"}

    def __init__(
        self,
        name: str = "audio_clip",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(name=name, source_path=source_path, uuid=uuid)
        self._clip: "AudioClip | None" = None
        self._chunk: ctypes.c_void_p | None = None

    @property
    def clip(self) -> "AudioClip | None":
        """Get AudioClip, loading it if needed."""
        if not self._loaded:
            self._load()
        return self._clip

    @property
    def resource(self) -> "AudioClip | None":
        """Get the underlying resource."""
        return self.clip

    def _load(self) -> bool:
        """Load audio data from source_path."""
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

        log.debug(f"[AudioClipAsset] Loaded: {self._name}")
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
        """Create AudioClipAsset from file path."""
        path = Path(path)
        if name is None:
            name = path.stem

        return cls(name=name, source_path=path, uuid=uuid)

    def __del__(self):
        """Ensure audio data is freed on garbage collection."""
        self.unload()
