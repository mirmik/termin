"""AudioListener component for receiving spatial audio."""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.core.component import Component
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene


class AudioListener(Component):
    """
    Component that represents the audio listener (ears) in the scene.

    Usually attached to the camera or player entity.
    There should typically be only one active AudioListener in a scene.
    """

    inspect_fields = {
        "volume": InspectField(
            path="volume",
            label="Master Volume",
            kind="float",
            min=0.0,
            max=1.0,
            step=0.01,
        ),
    }

    def __init__(self, volume: float = 1.0):
        super().__init__(enabled=True)
        self.volume: float = volume
        self._last_volume: float = volume

    def on_added(self, scene: "Scene") -> None:
        """Called when component is added to scene."""
        self._apply_volume()

    def start(self) -> None:
        """Called before first update."""
        super().start()
        self._apply_volume()

    def update(self, dt: float) -> None:
        """Update master volume if changed."""
        if self.volume != self._last_volume:
            self._apply_volume()
            self._last_volume = self.volume

    def _apply_volume(self) -> None:
        """Apply master volume to audio engine."""
        from termin.audio.audio_engine import AudioEngine

        engine = AudioEngine.instance()
        if engine.is_initialized:
            engine.set_master_volume(self.volume)
