"""Python facade over the canonical native audio runtime."""

from __future__ import annotations

import math

from termin.audio import _audio_native
from termin.audio._audio_native import TcAudioClip, TcAudioVoice


class AudioEngine:
    """Stateless facade; engine ownership and state live in ``termin_audio``."""

    def initialize(
        self,
        *,
        no_device: bool = False,
        sample_rate: int = 48_000,
        channels: int = 2,
    ) -> bool:
        return _audio_native.engine_initialize(no_device, sample_rate, channels)

    def shutdown(self) -> None:
        _audio_native.engine_shutdown()

    @property
    def is_initialized(self) -> bool:
        return _audio_native.engine_is_initialized()

    @property
    def is_available(self) -> bool:
        return _audio_native.engine_has_device()

    @property
    def sample_rate(self) -> int:
        return _audio_native.engine_sample_rate()

    @property
    def channels(self) -> int:
        return _audio_native.engine_channels()

    def create_voice(self, clip: TcAudioClip) -> TcAudioVoice:
        return TcAudioVoice.create(clip)

    def set_master_volume(self, volume: float) -> None:
        _audio_native.engine_set_master_volume(volume)

    def get_master_volume(self) -> float:
        return _audio_native.engine_get_master_volume()

    def set_listener_position(self, x: float, y: float, z: float) -> None:
        _audio_native.engine_set_listener_position(x, y, z)

    def set_listener_direction(self, x: float, y: float, z: float) -> None:
        _audio_native.engine_set_listener_direction(x, y, z)

    def set_listener_velocity(self, x: float, y: float, z: float) -> None:
        _audio_native.engine_set_listener_velocity(x, y, z)

    # Diagnostics expose occupied native voice slots without owning them.
    @property
    def num_channels(self) -> int:
        return _audio_native.voice_capacity()

    def is_channel_playing(self, channel: int) -> bool:
        return _audio_native.voice_is_playing_at(channel)

    def is_channel_paused(self, channel: int) -> bool:
        return _audio_native.voice_is_paused_at(channel)

    def get_channel_volume(self, channel: int) -> float:
        return _audio_native.voice_volume_at(channel)

    def get_channel_position(self, channel: int) -> tuple[float, float]:
        x, y, z = _audio_native.voice_position_at(channel)
        listener_x, listener_y, listener_z = _audio_native.engine_get_listener_position()
        offset_x = x - listener_x
        offset_y = y - listener_y
        offset_z = z - listener_z
        angle = math.degrees(math.atan2(offset_z, offset_x)) % 360.0
        distance = math.sqrt(offset_x**2 + offset_y**2 + offset_z**2)
        return angle, distance


__all__ = ["AudioEngine"]
