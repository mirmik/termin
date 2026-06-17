"""Audio subsystem for Termin."""

from __future__ import annotations

from termin.audio.audio_clip import AudioClip
from termin.audio.audio_engine import AudioEngine


def __getattr__(name: str):
    if name == "AudioClipAsset":
        from termin.audio.asset import AudioClipAsset

        globals()["AudioClipAsset"] = AudioClipAsset
        return AudioClipAsset

    if name == "AudioClipHandle":
        from termin.audio.handle import AudioClipHandle

        globals()["AudioClipHandle"] = AudioClipHandle
        return AudioClipHandle

    if name in ("AudioSource", "AudioListener"):
        from termin.audio.components import AudioListener, AudioSource

        exports = {
            "AudioSource": AudioSource,
            "AudioListener": AudioListener,
        }
        globals().update(exports)
        return exports[name]

    raise AttributeError(f"module 'termin.audio' has no attribute {name!r}")


__all__ = [
    "AudioEngine",
    "AudioClip",
    "AudioClipAsset",
    "AudioClipHandle",
    "AudioSource",
    "AudioListener",
]
