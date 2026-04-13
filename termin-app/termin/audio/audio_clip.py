"""AudioClip - audio data wrapper."""

from __future__ import annotations

import ctypes


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
