"""Класс отвечает за отрисовку визуальных эффектов текущего таймлайна."""

from __future__ import annotations
import traceback

from typing import TYPE_CHECKING, Any

from termin._native import log
from termin.visualization.core.component import PythonComponent
from termin.chronosquad.controllers.chronosphere_controller import ChronosphereController
from termin.chronosquad.core.effects.blind_effect import BlindEffect

if TYPE_CHECKING:
    from termin.chronosquad.core.event_line import EventCard


class EffectView:
    """Base class for visual effect views."""

    def __init__(self, scene: Any, effect: EventCard):
        self._visited = False

    def update(self, effect: EventCard, current_step: int) -> None:
        """Update the visual effect."""
        pass

    def destroy(self) -> None:
        """Clean up visual effect resources."""
        pass


class VisualEffectsController(PythonComponent):
    """
    Controller for managing visual effects in the timeline.

    Responsible for initializing, updating, and cleaning up visual effects
    associated with the timeline.
    """

    def __init__(
        self,
        enabled: bool = True,
    ):
        super().__init__(enabled=enabled)
        self._chronosphere_controller: ChronosphereController | None = None
        self._chronosphere = None
        self.views: dict = {}
        self._last_timeline = None

    def start(self) -> None:
        """Called when the controller is started."""
        self._chronosphere_controller = ChronosphereController.instance()
        if self._chronosphere_controller is None:
            log.error("[VisualEffectsController] ChronosphereController not found in scene.")
            return

        self._chronosphere = self._chronosphere_controller.chronosphere
        if self._chronosphere is None:
            log.error("[VisualEffectsController] Chronosphere not found in ChronosphereController.")

    def invalidate(self) -> None:
        """Invalidate all views when timeline changes."""
        for view in self.views.values():
            view.destroy()
        self.views.clear()

    def update(self, delta_time: float) -> None:
        """Update visual effects based on the timeline state."""
        if self._chronosphere is None:
            return

        try:
            timeline = self._chronosphere.current_timeline
            if timeline is None:
                return

            if self._last_timeline != timeline:
                self.invalidate()
                self._last_timeline = timeline

            current_step = timeline.current_step

            line = timeline._visual_effect_events
            active_effects = line.active_cards()

            for view in self.views.values():
                view._visited = False

            for effect in active_effects:
                view = None
                if effect in self.views:
                    view = self.views[effect]
                else:
                    view = self._init_new_effect(effect)

                if view is not None:
                    view.update(effect, current_step)
                    view._visited = True

            for effect, view in list(self.views.items()):
                if not view._visited:
                    view.destroy(self.scene)
                    del self.views[effect]

        except Exception as e:
            log.error(f"[VisualEffectsController] Error in update: {e}")
            traceback.print_exc()

    def _init_new_effect(self, effect: EventCard) -> EffectView | None:
        """Initialize a new visual effect view."""
        from termin.chronosquad.controllers.effects.blind_effect import BlindEffectView

        if isinstance(effect, BlindEffect):
            view = BlindEffectView(self.scene, effect)
            self.views[effect] = view
            log.info(f"[VisualEffectsController] Initialized BlindEffectView for effect at position {effect._position}")
            return view

        return None
