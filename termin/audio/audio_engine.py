"""AudioEngine - SDL_mixer wrapper for audio playback."""

from __future__ import annotations

from typing import TYPE_CHECKING

import ctypes

if TYPE_CHECKING:
    pass


class AudioEngine:
    """
    Singleton for SDL_mixer audio management.

    Handles initialization, channel management, and playback control.
    Must be initialized before any audio operations.
    """

    _instance: "AudioEngine | None" = None
    _creating_singleton: bool = False

    def __init__(self):
        if not AudioEngine._creating_singleton:
            raise RuntimeError(
                "AudioEngine is a singleton. Use AudioEngine.instance() instead."
            )

        self._initialized: bool = False
        self._mixer_available: bool = False

        # Audio settings
        self._frequency: int = 44100
        self._format: int = 0  # Will be set to MIX_DEFAULT_FORMAT
        self._channels_stereo: int = 2
        self._chunk_size: int = 2048
        self._num_channels: int = 32  # Mixing channels (not stereo channels)

        # SDL_mixer module reference (set on init)
        self._mixer = None

    @classmethod
    def instance(cls) -> "AudioEngine":
        """Get singleton instance."""
        if cls._instance is None:
            cls._creating_singleton = True
            try:
                cls._instance = cls()
            finally:
                cls._creating_singleton = False
        return cls._instance

    @classmethod
    def _reset_for_testing(cls) -> None:
        """Reset singleton instance. For testing only."""
        if cls._instance is not None:
            cls._instance.shutdown()
        cls._instance = None

    @property
    def is_initialized(self) -> bool:
        """True if audio engine is initialized and ready."""
        return self._initialized

    @property
    def is_available(self) -> bool:
        """True if SDL_mixer is available."""
        return self._mixer_available

    def initialize(self) -> bool:
        """
        Initialize SDL audio subsystem and SDL_mixer.

        Returns:
            True if initialization successful, False otherwise.
        """
        if self._initialized:
            return True

        # Try to import SDL_mixer
        try:
            from sdl2 import sdlmixer
            self._mixer = sdlmixer
            self._mixer_available = True
        except ImportError:
            print("[AudioEngine] SDL_mixer not available. Audio disabled.")
            self._mixer_available = False
            return False

        # Initialize SDL audio subsystem
        import sdl2
        if sdl2.SDL_InitSubSystem(sdl2.SDL_INIT_AUDIO) != 0:
            error = sdl2.SDL_GetError()
            print(f"[AudioEngine] Failed to init SDL audio: {error}")
            return False

        # Initialize SDL_mixer with format support
        init_flags = (
            sdlmixer.MIX_INIT_MP3 |
            sdlmixer.MIX_INIT_OGG |
            sdlmixer.MIX_INIT_FLAC
        )
        result = sdlmixer.Mix_Init(init_flags)
        if result == 0:
            # Mix_Init returns 0 on complete failure
            print("[AudioEngine] Warning: No audio format support initialized")

        # Open audio device
        self._format = sdlmixer.MIX_DEFAULT_FORMAT
        if sdlmixer.Mix_OpenAudio(
            self._frequency,
            self._format,
            self._channels_stereo,
            self._chunk_size
        ) < 0:
            error = sdlmixer.Mix_GetError()
            print(f"[AudioEngine] Failed to open audio: {error}")
            sdlmixer.Mix_Quit()
            return False

        # Allocate mixing channels
        sdlmixer.Mix_AllocateChannels(self._num_channels)

        self._initialized = True
        print(f"[AudioEngine] Initialized: {self._frequency}Hz, {self._num_channels} channels")
        return True

    def shutdown(self) -> None:
        """Shutdown audio engine and release resources."""
        if not self._initialized:
            return

        if self._mixer is not None:
            self._mixer.Mix_CloseAudio()
            self._mixer.Mix_Quit()

        import sdl2
        sdl2.SDL_QuitSubSystem(sdl2.SDL_INIT_AUDIO)

        self._initialized = False
        print("[AudioEngine] Shutdown complete")

    def load_chunk(self, path: str) -> ctypes.c_void_p | None:
        """
        Load audio file as Mix_Chunk.

        Args:
            path: Path to audio file (.wav, .ogg, .mp3, .flac)

        Returns:
            Mix_Chunk pointer or None on failure.
        """
        if not self._initialized:
            if not self.initialize():
                return None

        chunk = self._mixer.Mix_LoadWAV(path.encode("utf-8"))
        if not chunk:
            error = self._mixer.Mix_GetError()
            print(f"[AudioEngine] Failed to load '{path}': {error}")
            return None

        return chunk

    def free_chunk(self, chunk: ctypes.c_void_p) -> None:
        """Free a loaded Mix_Chunk."""
        if chunk and self._mixer is not None:
            self._mixer.Mix_FreeChunk(chunk)

    def play_chunk(
        self,
        chunk: ctypes.c_void_p,
        channel: int = -1,
        loops: int = 0,
        fade_in_ms: int = 0,
    ) -> int:
        """
        Play a Mix_Chunk on a channel.

        Args:
            chunk: Mix_Chunk pointer from load_chunk()
            channel: Channel to play on (-1 for first available)
            loops: Number of times to loop (-1 for infinite, 0 for once)
            fade_in_ms: Fade in duration in milliseconds

        Returns:
            Channel number playing on, or -1 on error.
        """
        if not self._initialized or chunk is None:
            return -1

        if fade_in_ms > 0:
            return self._mixer.Mix_FadeInChannel(channel, chunk, loops, fade_in_ms)
        return self._mixer.Mix_PlayChannel(channel, chunk, loops)

    def stop_channel(self, channel: int, fade_out_ms: int = 0) -> None:
        """
        Stop playback on a channel.

        Args:
            channel: Channel to stop (-1 for all channels)
            fade_out_ms: Fade out duration in milliseconds
        """
        if not self._initialized:
            return

        if fade_out_ms > 0:
            self._mixer.Mix_FadeOutChannel(channel, fade_out_ms)
        else:
            self._mixer.Mix_HaltChannel(channel)

    def pause_channel(self, channel: int) -> None:
        """Pause playback on a channel (-1 for all)."""
        if self._initialized:
            self._mixer.Mix_Pause(channel)

    def resume_channel(self, channel: int) -> None:
        """Resume playback on a channel (-1 for all)."""
        if self._initialized:
            self._mixer.Mix_Resume(channel)

    def is_channel_playing(self, channel: int) -> bool:
        """Check if a channel is currently playing."""
        if not self._initialized:
            return False
        return self._mixer.Mix_Playing(channel) == 1

    def is_channel_paused(self, channel: int) -> bool:
        """Check if a channel is paused."""
        if not self._initialized:
            return False
        return self._mixer.Mix_Paused(channel) == 1

    def set_channel_volume(self, channel: int, volume: float) -> None:
        """
        Set volume for a channel.

        Args:
            channel: Channel number (-1 for all)
            volume: Volume level (0.0 to 1.0)
        """
        if not self._initialized:
            return

        # SDL_mixer uses 0-128 volume range
        sdl_volume = int(max(0.0, min(1.0, volume)) * 128)
        self._mixer.Mix_Volume(channel, sdl_volume)

    def get_channel_volume(self, channel: int) -> float:
        """Get current volume for a channel (0.0 to 1.0)."""
        if not self._initialized:
            return 0.0

        # Pass -1 as volume to query current volume
        sdl_volume = self._mixer.Mix_Volume(channel, -1)
        return sdl_volume / 128.0

    def set_channel_position(
        self,
        channel: int,
        angle: int,
        distance: int,
    ) -> bool:
        """
        Set 3D position for a channel (panning and distance).

        Args:
            channel: Channel number
            angle: Angle in degrees (0 = front, 90 = right, 180 = back, 270 = left)
            distance: Distance (0 = close/loud, 255 = far/quiet)

        Returns:
            True if successful.
        """
        if not self._initialized:
            return False

        # Normalize angle to 0-360
        angle = angle % 360
        if angle < 0:
            angle += 360

        # Clamp distance
        distance = max(0, min(255, distance))

        return self._mixer.Mix_SetPosition(channel, angle, distance) != 0

    def set_master_volume(self, volume: float) -> None:
        """
        Set master volume for all channels.

        Args:
            volume: Volume level (0.0 to 1.0)
        """
        if not self._initialized:
            return

        sdl_volume = int(max(0.0, min(1.0, volume)) * 128)
        self._mixer.Mix_MasterVolume(sdl_volume)

    def get_master_volume(self) -> float:
        """Get current master volume (0.0 to 1.0)."""
        if not self._initialized:
            return 0.0

        sdl_volume = self._mixer.Mix_MasterVolume(-1)
        return sdl_volume / 128.0

    @property
    def num_channels(self) -> int:
        """Number of allocated mixing channels."""
        return self._num_channels

    def allocate_channels(self, num: int) -> int:
        """
        Set number of mixing channels.

        Args:
            num: Number of channels to allocate

        Returns:
            Actual number of channels allocated.
        """
        if not self._initialized:
            return 0

        self._num_channels = self._mixer.Mix_AllocateChannels(num)
        return self._num_channels
