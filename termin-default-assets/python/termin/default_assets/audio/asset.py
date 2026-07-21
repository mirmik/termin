"""Audio clip asset model."""

from __future__ import annotations

from pathlib import Path

from tcbase import log
from termin_assets import Asset
from termin.audio import TcAudioClip


class AudioClipAsset(Asset):
    """
    Asset for audio files decoded by the native runtime (.wav, .mp3, .flac).

    The asset declares a canonical ``TcAudioClip`` by UUID. The native audio
    registry owns decoded PCM and its lifetime.
    """

    SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".flac"}

    def __init__(
        self,
        name: str = "audio_clip",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(name=name, source_path=source_path, uuid=uuid)
        path = str(self._source_path) if self._source_path is not None else ""
        self._clip = TcAudioClip.declare(self.uuid, self._name, path)
        if not self._clip.is_valid:
            raise RuntimeError(f"Failed to declare native audio clip '{self.uuid}'")

    @property
    def clip(self) -> TcAudioClip:
        """Get AudioClip, loading it if needed."""
        if not self._loaded:
            self._load()
        self._loaded = self._clip.is_loaded
        return self._clip

    @property
    def resource(self) -> TcAudioClip:
        """Get the underlying resource."""
        return self.clip

    def _load(self) -> bool:
        """Load audio data from source_path."""
        if self._loaded:
            return True

        if self._source_path is None:
            return False

        self._clip.set_source_path(str(self._source_path))
        if not self._clip.load_file():
            log.error(f"[AudioClipAsset] Failed to load: {self._source_path}")
            return False
        self._loaded = True
        self._bump_version()

        log.debug(f"[AudioClipAsset] Loaded: {self._name}")
        return True

    def unload(self) -> None:
        """Unload audio data to free memory."""
        if self._clip.is_loaded and not self._clip.unload():
            log.error(f"[AudioClipAsset] Cannot unload active clip: {self.uuid}")
            return
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

    @Asset.source_path.setter
    def source_path(self, value: Path | str | None) -> None:
        self._source_path = Path(value) if value else None
        if self._source_path is not None:
            self._clip.set_source_path(str(self._source_path))

    def _rename(self, value: str) -> None:
        super()._rename(value)
        self._clip.set_name(value)

    def _adopt_uuid(self, uuid: str) -> None:
        previous_uuid = self.uuid
        super()._adopt_uuid(uuid)
        if uuid == previous_uuid:
            return
        path = str(self._source_path) if self._source_path is not None else ""
        replacement = TcAudioClip.declare(uuid, self._name, path)
        if not replacement.is_valid:
            log.error(f"[AudioClipAsset] Failed to adopt native UUID '{uuid}'")
            raise RuntimeError(f"Failed to declare native audio clip '{uuid}'")
        self._clip = replacement
