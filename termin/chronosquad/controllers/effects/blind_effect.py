from termin.chronosquad.core.effects.blind_effect import BlindEffect
from termin.visualization.core.resource_manager import ResourceManager
from termin.visualization.core.mesh_renderer import MeshRenderer
from termin.chronosquad.controllers.visual_effects_controller import EffectView

class BlindEffectView(EffectView):
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