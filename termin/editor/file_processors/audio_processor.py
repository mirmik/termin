"""Audio file pre-loader for audio files."""

from __future__ import annotations

from typing import Set

from termin.editor.project_file_watcher import FilePreLoader, PreLoadResult


class AudioPreLoader(FilePreLoader):
    """Pre-loads audio files - reads UUID from spec (lazy loading)."""

    @property
    def priority(self) -> int:
        return 10  # Audio files have no dependencies (like textures)

    @property
    def extensions(self) -> Set[str]:
        return {".wav", ".ogg", ".mp3", ".flac"}

    @property
    def resource_type(self) -> str:
        return "audio_clip"

    def preload(self, path: str) -> PreLoadResult | None:
        """
        Pre-load audio file: only read UUID from spec (lazy loading).
        """
        # Read spec file (may contain uuid)
        spec_data = self.read_spec_file(path)
        uuid = spec_data.get("uuid") if spec_data else None

        return PreLoadResult(
            resource_type=self.resource_type,
            path=path,
            content=None,  # Lazy loading - don't read content
            uuid=uuid,
            spec_data=spec_data,
        )


# Backward compatibility alias
AudioFileProcessor = AudioPreLoader
