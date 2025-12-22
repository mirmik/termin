"""AudioSource component for playing audio clips."""

from __future__ import annotations

import numpy as np
from typing import TYPE_CHECKING

from termin.visualization.core.component import Component
from termin.editor.inspect_field import InspectField
from termin.assets.audio_clip_handle import AudioClipHandle

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.audio.components.audio_listener import AudioListener


class AudioSource(Component):
    """
    Component for playing audio clips.

    Supports 2D and 3D spatial audio with distance attenuation.
    """

    inspect_fields = {
        "clip": InspectField(
            path="clip",
            label="Audio Clip",
            kind="audio_clip",
            setter=lambda obj, val: obj.set_clip(val),
        ),
        "volume": InspectField(
            path="volume",
            label="Volume",
            kind="float",
            min=0.0,
            max=1.0,
            step=0.01,
        ),
        "pitch": InspectField(
            path="pitch",
            label="Pitch",
            kind="float",
            min=0.1,
            max=3.0,
            step=0.01,
        ),
        "loop": InspectField(
            path="loop",
            label="Loop",
            kind="bool",
        ),
        "play_on_awake": InspectField(
            path="play_on_awake",
            label="Play On Awake",
            kind="bool",
        ),
        "spatial_blend": InspectField(
            path="spatial_blend",
            label="Spatial Blend",
            kind="float",
            min=0.0,
            max=1.0,
            step=0.01,
        ),
        "min_distance": InspectField(
            path="min_distance",
            label="Min Distance",
            kind="float",
            min=0.0,
            max=100.0,
            step=0.1,
        ),
        "max_distance": InspectField(
            path="max_distance",
            label="Max Distance",
            kind="float",
            min=0.1,
            max=500.0,
            step=1.0,
        ),
    }

    def __init__(
        self,
        clip: AudioClipHandle | None = None,
        volume: float = 1.0,
        pitch: float = 1.0,
        loop: bool = False,
        play_on_awake: bool = False,
        spatial_blend: float = 0.0,
        min_distance: float = 1.0,
        max_distance: float = 50.0,
    ):
        super().__init__(enabled=True)

        # Serialized properties
        self.clip: AudioClipHandle | None = clip
        self.volume: float = volume
        self.pitch: float = pitch
        self.loop: bool = loop
        self.play_on_awake: bool = play_on_awake
        self.spatial_blend: float = spatial_blend
        self.min_distance: float = min_distance
        self.max_distance: float = max_distance

        # Runtime state (not serialized)
        self._channel: int = -1
        self._is_playing: bool = False
        self._is_paused: bool = False

    def set_clip(self, clip: AudioClipHandle | None) -> None:
        """Set the audio clip. Stops playback if currently playing."""
        if self._is_playing:
            self.stop()
        self.clip = clip

    def on_added(self, scene: "Scene") -> None:
        """Called when component is added to scene."""
        if self.play_on_awake and self.clip is not None:
            self.play()

    def on_removed(self) -> None:
        """Called when component is removed."""
        self.stop()

    def start(self) -> None:
        """Called before first update."""
        super().start()
        # play_on_awake is handled in on_added for immediate playback

    def play(self) -> None:
        """Start playing the audio clip."""
        if self.clip is None:
            return

        # Get AudioClip from handle (lazy loads if needed)
        audio_clip = self.clip.get()
        if audio_clip is None or not audio_clip.is_valid:
            return

        from termin.audio.audio_engine import AudioEngine

        engine = AudioEngine.instance()
        if not engine.is_initialized:
            if not engine.initialize():
                return

        # Stop current playback if any
        if self._channel >= 0:
            engine.stop_channel(self._channel)

        loops = -1 if self.loop else 0
        self._channel = engine.play_chunk(audio_clip.chunk, loops=loops)

        if self._channel >= 0:
            engine.set_channel_volume(self._channel, self.volume)
            self._is_playing = True
            self._is_paused = False

    def stop(self, fade_out_ms: int = 0) -> None:
        """Stop playback."""
        if self._channel < 0:
            return

        from termin.audio.audio_engine import AudioEngine

        engine = AudioEngine.instance()
        engine.stop_channel(self._channel, fade_out_ms)
        self._channel = -1
        self._is_playing = False
        self._is_paused = False

    def pause(self) -> None:
        """Pause playback."""
        if self._channel < 0 or not self._is_playing:
            return

        from termin.audio.audio_engine import AudioEngine

        AudioEngine.instance().pause_channel(self._channel)
        self._is_paused = True

    def resume(self) -> None:
        """Resume paused playback."""
        if self._channel < 0 or not self._is_paused:
            return

        from termin.audio.audio_engine import AudioEngine

        AudioEngine.instance().resume_channel(self._channel)
        self._is_paused = False

    @property
    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        if self._channel < 0:
            return False

        from termin.audio.audio_engine import AudioEngine

        return AudioEngine.instance().is_channel_playing(self._channel)

    @property
    def is_paused(self) -> bool:
        """Check if audio is paused."""
        return self._is_paused

    def update(self, dt: float) -> None:
        """Update spatial audio positioning."""
        if not self._is_playing or self._channel < 0:
            return

        # Check if playback finished naturally
        if not self.is_playing and not self._is_paused:
            self._is_playing = False
            self._channel = -1
            return

        # Update volume if changed
        from termin.audio.audio_engine import AudioEngine
        engine = AudioEngine.instance()
        engine.set_channel_volume(self._channel, self.volume)

        # Skip spatial processing for 2D sounds
        if self.spatial_blend <= 0.0:
            return

        listener = self._find_audio_listener()
        if listener is None:
            return

        self._update_spatial_audio(listener, engine)

    def _find_audio_listener(self) -> "AudioListener | None":
        """Find the AudioListener in the scene."""
        if self.entity is None or self.entity.scene is None:
            return None

        from termin.audio.components.audio_listener import AudioListener

        for entity in self.entity.scene.entities:
            listener = entity.get_component(AudioListener)
            if listener is not None and listener.enabled:
                return listener
        return None

    def _update_spatial_audio(self, listener: "AudioListener", engine) -> None:
        """Update 3D audio positioning based on listener."""
        if self.entity is None or listener.entity is None:
            return

        # Get world positions
        source_pos = self.entity.world_transform.position
        listener_pos = listener.entity.world_transform.position

        # Calculate distance
        to_source = source_pos - listener_pos
        distance = np.linalg.norm(to_source)

        # Calculate SDL distance (0 = close, 255 = far)
        if distance <= self.min_distance:
            sdl_distance = 0
        elif distance >= self.max_distance:
            sdl_distance = 255
        else:
            t = (distance - self.min_distance) / (self.max_distance - self.min_distance)
            sdl_distance = int(t * 255)

        # Calculate angle relative to listener
        if distance > 0.001:
            to_source_norm = to_source / distance

            # Get listener forward direction
            listener_forward = listener.entity.world_transform.forward

            # Calculate angle in XZ plane (horizontal)
            angle_rad = np.arctan2(to_source_norm[0], to_source_norm[2])
            listener_angle = np.arctan2(listener_forward[0], listener_forward[2])
            relative_angle = angle_rad - listener_angle
            angle_deg = int(np.degrees(relative_angle)) % 360
        else:
            angle_deg = 0

        # Apply spatial blend
        final_distance = int(sdl_distance * self.spatial_blend)

        engine.set_channel_position(self._channel, angle_deg, final_distance)
