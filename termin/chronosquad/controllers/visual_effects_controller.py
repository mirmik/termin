"""Класс отвечает за отрисовку визуальных эффектов текущего тамлайна."""

from __future__ import annotations
import traceback


from typing import TYPE_CHECKING

from termin._native import log
from termin.visualization.core.component import PythonComponent
from termin.chronosquad.core import Vec3

from termin.chronosquad.controllers.object_controller import ObjectController
from termin.chronosquad.controllers.action.action_component import ClickInfo
from termin.chronosquad.controllers.action_server_component import ActionServerComponent
from termin.chronosquad.controllers.visual_effect import VisualEffect

if TYPE_CHECKING:
    from termin.chronosquad.controllers.object_controller import ObjectController
    from termin.chronosquad.controllers.chronosphere_controller import ChronosphereController

class EffectView:
    """Base class for visual effect views."""
    def __init__(self, scene, effect: VisualEffect):
        self._visited = False

class BlindEffectView:
    """View for rendering BlindEffect visual effects."""

    def __init__(self, scene, effect: BlindEffect):
        # Initialize visual effect resources here
        entity = scene.create_entity(f"BlindEffect_{id(effect)}")
        self._entity = entity
        self._start_step = effect.start_step
        self._finish_step = effect.finish_step

        rm = ResourceManager.instance()

        entity.transform.position = effect._position
        self.material = rm.get_material("BlindEffectMaterial").copy()
        sphere_mesh = rm.get_mesh("Sphere")
        mr = entity.add_component(MeshRenderer(mesh=sphere_mesh, material=material))
        print("BlindEffectView created at position:", effect._position)

    def intensivity(self, stepstamp)
    {
        center = (self._finish_step - self._start_step) / 2;
        a = (stepstamp - self._start_step) - center;
        return 1 - Math.Abs(a / center);
    }

    def update(self, effect: BlindEffect, current_step: int) -> None:
        """Update the visual effect based on the effect state and current step."""
        self.material.set_param("intensivity", self.intensivity(current_step))
        
    def destroy(self) -> None:
        """Clean up visual effect resources."""
        self._entity.destroy()
        print("BlindEffectView destroyed")

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
        # Initialize any necessary state here

    def start(self) -> None:
        """Called when the controller is started."""
        
        self._chronosphere_controller = ChronoController.instance()
        if self._chronosphere_controller is None:
            log.error("[VisualEffectsController] ChronosphereController not found in scene.")

        self._chronosphere = self._chronosphere_controller.chronosphere
        if self._chronosphere is None:
            log.error("[VisualEffectsController] Chronosphere not found in ChronosphereController.")

        self.views = {}
        self._last_timeline = None

    def invalidate(self) -> None:
        pass

    def update(self, delta_time: float) -> None:
        """Update visual effects based on the timeline state."""
        try:
            timeline = self._chronosphere.current_timeline()
            if timeline is None:
                return

            if self._last_timeline != timeline:
                self.invalidate()
                self._last_timeline = timeline

            current_step = timeline.current_step

            line = timeline.visual_effects 
            active_effects = line.actives()

            for view in self.views.values():
                view._visited = False

            for effect in active_effects:
                view = None
                if effect in self.views:
                    view = self.views[effect]
                else:
                    view = self.init_new_effect(effect)
                
                view.update(effect, current_step)
                view._visited = True
                
            for effect, view in list(self.views.items()):
                if not view._visited:
                    self.views[effect].destroy()
                    del self.views[effect]

        except Exception as e:
            log.error(f"[VisualEffectsController] Error in update: {e}")
            traceback.print_exc()

    def init_new_effect(self, effect: VisualEffect) -> None:
        """Initialize a new visual effect view."""
        if isinstance(effect, BlindEffect):
            view = BlindEffectView(self.scene, effect)
            self.views[effect] = view
            log.info(f"[VisualEffectsController] Initialized BlindEffectView for effect at position {effect._position}")
