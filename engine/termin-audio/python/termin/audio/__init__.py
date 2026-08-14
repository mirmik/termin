"""Audio subsystem for Termin."""

from __future__ import annotations

from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("termin_audio")

from termin.audio._audio_native import TcAudioClip, TcAudioVoice
from termin.audio.audio_engine import AudioEngine
from termin.audio.components import AudioListener, AudioSource


__all__ = [
    "AudioEngine",
    "TcAudioClip",
    "TcAudioVoice",
    "AudioSource",
    "AudioListener",
]
