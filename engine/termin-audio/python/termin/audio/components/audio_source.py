"""AudioSource component for playing audio clips."""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.scene import PythonComponent
from termin.inspect import InspectField
from tcbase import log
from termin.audio import AudioEngine, TcAudioClip, TcAudioVoice

if TYPE_CHECKING:
    from termin.audio.components.audio_listener import AudioListener


def _inspect_audio_clip(component: "AudioSource") -> dict[str, str | None] | None:
    clip = component.clip
    if clip is None or not clip.is_valid:
        return None
    return {"uuid": clip.uuid, "name": clip.name}


def _set_inspect_audio_clip(component: "AudioSource", value: dict[str, str | None] | None) -> None:
    if value is None:
        component.set_clip(None)
        return
    uuid = value.get("uuid")
    if uuid:
        clip = TcAudioClip.from_uuid(uuid)
        if clip.is_valid:
            component.set_clip(clip)
            return
        log.error(f"[AudioSource] Audio clip UUID '{uuid}' is not declared")
    elif value.get("name"):
        log.error("[AudioSource] Refusing name-only audio clip reference; UUID is required")
    component.set_clip(None)


class AudioSource(PythonComponent):
    """
    Component for playing audio clips.

    Supports 2D and 3D spatial audio with distance attenuation.
    """

    component_category = "Audio"

    inspect_fields = {
        "clip": InspectField(
            path="clip",
            label="Audio Clip",
            kind="audio_clip_handle",
            getter=_inspect_audio_clip,
            setter=_set_inspect_audio_clip,
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
        clip: TcAudioClip | None = None,
        volume: float = 1.0,
        pitch: float = 1.0,
        loop: bool = False,
        play_on_awake: bool = False,
        spatial_blend: float = 0.0,
        min_distance: float = 1.0,
        max_distance: float = 50.0,
    ):
        super().__init__(enabled=True)

        self.clip: TcAudioClip | None = clip
        self.volume: float = volume
        self.pitch: float = pitch
        self.loop: bool = loop
        self.play_on_awake: bool = play_on_awake
        self.spatial_blend: float = spatial_blend
        self.min_distance: float = min_distance
        self.max_distance: float = max_distance

        self._voice: TcAudioVoice | None = None

    def set_clip(self, clip: TcAudioClip | None) -> None:
        """Set the audio clip. Stops playback if currently playing."""
        if self._voice is not None:
            self.stop()
        self.clip = clip

    def on_added(self) -> None:
        """Called when component is added."""
        if self.play_on_awake and self.clip is not None:
            self.play()

    def on_removed(self) -> None:
        """Called when component is removed."""
        self.stop()

    def start(self) -> None:
        """Called before first update."""
        super().start()

    def play(self) -> None:
        """Start playing the audio clip."""
        if self.clip is None:
            return

        if not self.clip.is_valid or not self.clip.ensure_loaded():
            return

        engine = AudioEngine()
        if not engine.is_initialized:
            if not engine.initialize():
                return

        if self._voice is not None:
            self.stop()

        voice = engine.create_voice(self.clip)
        if not voice.is_valid:
            log.error(f"[AudioSource] Failed to create voice for clip '{self.clip.uuid}'")
            return
        voice.looping = self.loop
        voice.volume = self.volume
        voice.pitch = self.pitch
        voice.set_spatialization(self.spatial_blend > 0.0)
        voice.set_distance_range(self.min_distance, self.max_distance)
        if not voice.start():
            log.error(f"[AudioSource] Failed to start voice for clip '{self.clip.uuid}'")
            voice.destroy()
            return
        self._voice = voice

    def stop(self, fade_out_ms: int = 0) -> None:
        """Stop playback."""
        if self._voice is None:
            return
        self._voice.stop(fade_out_ms)
        if fade_out_ms == 0:
            self._voice.destroy()
            self._voice = None

    def pause(self) -> None:
        """Pause playback."""
        if self._voice is not None and self._voice.is_playing:
            self._voice.pause()

    def resume(self) -> None:
        """Resume paused playback."""
        if self._voice is not None and self._voice.is_paused:
            self._voice.resume()

    @property
    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        return self._voice is not None and self._voice.is_playing

    @property
    def is_paused(self) -> bool:
        """Check if audio is paused."""
        return self._voice is not None and self._voice.is_paused

    def update(self, dt: float) -> None:
        """Update spatial audio positioning."""
        voice = self._voice
        if voice is None:
            return

        if not voice.is_playing and not voice.is_paused:
            voice.destroy()
            self._voice = None
            return

        voice.volume = self.volume
        voice.pitch = self.pitch
        voice.looping = self.loop
        voice.set_spatialization(self.spatial_blend > 0.0)
        voice.set_distance_range(self.min_distance, self.max_distance)

        if self.spatial_blend <= 0.0:
            return

        listener = self._find_audio_listener()
        if listener is None:
            return

        self._update_spatial_audio(listener, AudioEngine(), voice)

    def _find_audio_listener(self) -> "AudioListener | None":
        """Find the AudioListener in the scene."""
        if self.entity is None:
            return None
        scene = self.entity.scene
        if scene is None:
            return None

        from termin.audio.components.audio_listener import AudioListener

        for entity in scene.get_all_entities():
            listener = entity.get_component(AudioListener)
            if listener is not None and listener.enabled:
                return listener
        return None

    def _update_spatial_audio(
        self,
        listener: "AudioListener",
        engine: AudioEngine,
        voice: TcAudioVoice,
    ) -> None:
        """Update 3D audio positioning based on listener."""
        if self.entity is None or listener.entity is None:
            return

        source_pos = self.entity.world_transform.position
        listener_pos = listener.entity.world_transform.position

        listener_forward = listener.entity.world_transform.forward
        engine.set_listener_position(listener_pos.x, listener_pos.y, listener_pos.z)
        engine.set_listener_direction(listener_forward.x, listener_forward.y, listener_forward.z)

        blended_position = listener_pos + (source_pos - listener_pos) * self.spatial_blend
        voice.set_position(blended_position.x, blended_position.y, blended_position.z)
