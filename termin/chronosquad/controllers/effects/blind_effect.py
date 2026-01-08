from termin.chronosquad.core.effects.blind_effect import BlindEffect
from termin.assets import ResourceManager
from termin.visualization.render.components.mesh_renderer import MeshRenderer
from termin.chronosquad.controllers.visual_effects_controller import EffectView
from termin.geombase import Pose3, Vec3
import numpy


class BlindEffectView(EffectView):
    """View for rendering BlindEffect visual effects."""

    def __init__(self, scene, effect: BlindEffect):
        super().__init__(scene, effect)
        # Initialize visual effect resources here
        entity = scene.create_entity(f"BlindEffect_{id(effect)}")
        self._entity = entity
        self._start_step = effect.start_step
        self._finish_step = effect.finish_step

        rm = ResourceManager.instance()

        entity.transform.relocate(Pose3(lin=effect._position))
        self.material = rm.get_material("BlindEffectMaterial").copy()
        self.update_color(effect.start_step)
        sphere_mesh = rm.get_mesh("Sphere")
        mr = entity.add_component(MeshRenderer(mesh=sphere_mesh, material=self.material))

        entity.transform.set_local_scale(Vec3(1.4, 1.4, 1.4))

        print("BlindEffectView created at position:", effect._position)

    def update_color(self, stepstamp: int) -> None:
        """Update the color of the blind effect based on the current stepstamp."""
        color = self.material.color
        intensity = self.intensivity(stepstamp)
        color.w = intensity  # Update alpha based on intensity
        self.material.color = color

    def intensivity(self, stepstamp: int) -> float:
        """Get blink effect intensity (0 at edges, 1 at center)."""
        center = (self._finish_step - self._start_step) / 2
        a = (stepstamp - self._start_step) - center
        return 1 - abs(a / center) if center > 0 else 0

    def update(self, effect: BlindEffect, current_step: int) -> None:
        """Update the visual effect based on the effect state and current step."""
        intensity = self.intensivity(current_step)
        self.update_color(current_step)
        print(f"BlindEffectView updated at step {current_step} with intensity {intensity}")

    def destroy(self, scene) -> None:
        """Clean up visual effect resources."""
        scene.remove(self._entity)
        print("BlindEffectView destroyed")