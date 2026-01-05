"""GameController - handles game input for time control."""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin._native import log
from termin.visualization.core.component import InputComponent
from termin.visualization.core.input_events import KeyEvent, ScrollEvent
from termin.visualization.platform.backends.base import Key, Action

if TYPE_CHECKING:
    from .chronosphere_controller import ChronosphereController


# Modifier key masks (standard GLFW/SDL values)
MOD_SHIFT = 0x0001


class GameController(InputComponent):
    """
    Handles game input for controlling time.

    - Space: Toggle pause
    - Shift + Scroll: Change time speed / rewind
    """

    # Speed presets (from fast forward to rewind)
    SPEEDS = [4.0, 2.0, 1.0, 0.3, 0.1, 0.0, -0.1, -0.3, -1.0, -2.0]
    DEFAULT_SPEED_INDEX = 2  # 1.0x

    def __init__(self, enabled: bool = True):
        super().__init__(enabled=enabled)
        self._chronosphere_controller: ChronosphereController | None = None
        self._current_speed_index = self.DEFAULT_SPEED_INDEX
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Find ChronosphereController if not yet initialized."""
        if self._initialized:
            return
        self._find_chronosphere_controller()
        self._initialized = True

    def _find_chronosphere_controller(self) -> None:
        """Find ChronosphereController in scene."""
        if self._scene is None:
            return

        from .chronosphere_controller import ChronosphereController

        for entity in self._scene.entities:
            ctrl = entity.get_component(ChronosphereController)
            if ctrl is not None:
                self._chronosphere_controller = ctrl
                log.info("[GameController] Found ChronosphereController")
                return

    @property
    def chronosphere(self):
        """Get the ChronoSphere."""
        if self._chronosphere_controller is None:
            return None
        return self._chronosphere_controller.chronosphere

    def on_key(self, event: KeyEvent) -> None:
        """Handle keyboard events."""
        # Only handle key press
        if event.action != Action.PRESS:
            return

        self._ensure_initialized()

        if event.key == Key.SPACE:
            self._on_space_pressed()

    def on_scroll(self, event: ScrollEvent) -> None:
        """Handle scroll events."""
        # Only with Shift held
        if not (event.viewport and hasattr(event, 'mods')):
            # For events without mods, check if shift is currently pressed
            # This is a fallback - ideally mods should be in the event
            pass

        self._ensure_initialized()

        # Shift + scroll = time control
        # Note: ScrollEvent doesn't have mods, so we handle all scroll for now
        # In practice, you might want to check a global keyboard state
        self._on_scroll_time_control(event.yoffset)

    def _on_space_pressed(self) -> None:
        """Toggle pause."""
        cs = self.chronosphere
        if cs is None:
            return

        cs.toggle_pause()
        is_paused = cs.is_paused
        log.info(f"[GameController] {'Paused' if is_paused else 'Resumed'}")

    def _on_scroll_time_control(self, y: float) -> None:
        """
        Handle time control via scroll wheel.

        When not paused: change speed preset
        When paused: scrub through time
        """
        cs = self.chronosphere
        if cs is None:
            return

        if not cs.is_paused:
            # Change speed preset
            if y > 0:
                # Scroll up = faster (lower index)
                self._current_speed_index = max(0, self._current_speed_index - 1)
            else:
                # Scroll down = slower/rewind (higher index)
                self._current_speed_index = min(
                    len(self.SPEEDS) - 1,
                    self._current_speed_index + 1
                )

            new_speed = self.SPEEDS[self._current_speed_index]
            cs.target_time_multiplier = new_speed
            log.info(f"[GameController] Speed: {new_speed}x")
        else:
            # Scrub time in pause mode
            modifier = 0.2 if y > 0 else -0.2
            # TODO: Implement time scrubbing in ChronoSphere
            # cs.modify_target_time_in_pause_mode(modifier)
            log.info(f"[GameController] Time scrub: {modifier}")

    def reset_speed(self) -> None:
        """Reset to normal speed (1.0x)."""
        self._current_speed_index = self.DEFAULT_SPEED_INDEX
        cs = self.chronosphere
        if cs is not None:
            cs.target_time_multiplier = 1.0
