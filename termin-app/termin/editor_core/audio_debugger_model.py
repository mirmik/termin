"""Toolkit-neutral audio engine diagnostics snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from termin.editor_core.signal import Signal


class AudioEngineDiagnostics(Protocol):
    @property
    def is_initialized(self) -> bool: ...

    @property
    def num_channels(self) -> int: ...

    def get_master_volume(self) -> float: ...

    def is_channel_playing(self, channel: int) -> bool: ...

    def get_channel_volume(self, channel: int) -> float: ...

    def get_channel_position(self, channel: int) -> tuple[float, float]: ...

    def is_channel_paused(self, channel: int) -> bool: ...


@dataclass(frozen=True)
class AudioChannelSnapshot:
    channel: int
    volume: float
    angle: float
    distance: float
    paused: bool


@dataclass(frozen=True)
class AudioDebuggerSnapshot:
    initialized: bool
    master_volume: float | None
    total_channels: int
    channels: tuple[AudioChannelSnapshot, ...]


class AudioDebuggerController:
    def __init__(self, engine: AudioEngineDiagnostics) -> None:
        self._engine = engine
        self.changed = Signal()

    def snapshot(self) -> AudioDebuggerSnapshot:
        if not self._engine.is_initialized:
            return AudioDebuggerSnapshot(False, None, 0, ())
        total = self._engine.num_channels
        active = []
        for channel in range(total):
            if not self._engine.is_channel_playing(channel):
                continue
            angle, distance = self._engine.get_channel_position(channel)
            active.append(
                AudioChannelSnapshot(
                    channel=channel,
                    volume=self._engine.get_channel_volume(channel),
                    angle=angle,
                    distance=distance,
                    paused=self._engine.is_channel_paused(channel),
                )
            )
        channels = tuple(active)
        return AudioDebuggerSnapshot(True, self._engine.get_master_volume(), total, channels)

    def refresh(self) -> AudioDebuggerSnapshot:
        snapshot = self.snapshot()
        self.changed.emit(snapshot)
        return snapshot


def create_audio_debugger_controller() -> AudioDebuggerController:
    from termin.audio.audio_engine import AudioEngine

    return AudioDebuggerController(AudioEngine.instance())


__all__ = [
    "AudioChannelSnapshot",
    "AudioDebuggerController",
    "AudioDebuggerSnapshot",
    "AudioEngineDiagnostics",
    "create_audio_debugger_controller",
]
