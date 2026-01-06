"""TimeModifierController - connects ChronoSphere time to post-process shader."""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin._native import log
from termin.visualization.core.python_component import PythonComponent

if TYPE_CHECKING:
    from .chronosphere_controller import ChronosphereController
    from termin.visualization.render.posteffects.material_effect import MaterialPostEffect
    from termin.visualization.core.shader import ShaderProgram
    from termin.visualization.core.camera import CameraComponent


class TimeModifierController(PythonComponent):
    """
    Connects ChronoSphere time_multiplier to the TimeModifier post-process shader.

    Must be placed on a camera entity with ViewportHintComponent.
    Finds ChronosphereController in the scene and MaterialPostEffect with
    TimeModifier material in the pipeline. Sets the before_draw callback
    to write u_time_modifier, u_near, u_far uniforms.
    """

    def __init__(self, enabled: bool = True):
        super().__init__(enabled=enabled)
        self._chronosphere_controller: ChronosphereController | None = None
        self._camera: CameraComponent | None = None
        self._time_effect: MaterialPostEffect | None = None
        self._initialized = False

    def start(self) -> None:
        """Find controllers and set up callback."""
        if self._initialized:
            return

        print("Starting TimeModifierController initialization...")

        self._find_camera()
        self._find_chronosphere_controller()
        self._find_time_effect()

        if self._time_effect is not None:
            self._time_effect.set_before_draw(self._before_draw)
            log.info("[TimeModifierController] Connected to TimeModifier effect")
        else:
            log.warning("[TimeModifierController] TimeModifier effect not found; cannot connect")

        self._initialized = True

    def _find_camera(self) -> None:
        """Find CameraComponent on this entity."""
        from termin.visualization.core.camera import CameraComponent

        if self._entity is None:
            return

        self._camera = self._entity.get_component(CameraComponent)
        if self._camera is None:
            log.warning("[TimeModifierController] CameraComponent not found on entity")

    def _find_chronosphere_controller(self) -> None:
        """Find ChronosphereController in scene."""
        from .chronosphere_controller import ChronosphereController

        if self._scene is None:
            return

        for entity in self._scene.entities:
            comp = entity.get_component(ChronosphereController)
            if comp is not None:
                self._chronosphere_controller = comp
                log.info(f"[TimeModifierController] Found ChronosphereController on '{entity.name}'")
                return

        log.warning("[TimeModifierController] ChronosphereController not found in scene")

    def _find_time_effect(self) -> None:
        """Find MaterialPostEffect named 'TimeSpection' in 'PostFX' pass."""
        from termin.visualization.core.viewport_hint import ViewportHintComponent
        from termin.visualization.render.postprocess import PostProcessPass
        from termin.visualization.render.posteffects.material_effect import MaterialPostEffect

        if self._entity is None:
            log.warning("[TimeModifierController] No entity")
            return

        hint = self._entity.get_component(ViewportHintComponent)
        if hint is None:
            log.warning("[TimeModifierController] ViewportHintComponent not found on entity")
            return

        pipeline = hint.get_pipeline()
        if pipeline is None:
            log.warning("[TimeModifierController] Pipeline not found")
            return

        # Find PostFX pass
        for render_pass in pipeline.passes:
            if not isinstance(render_pass, PostProcessPass):
                continue
            if render_pass.pass_name != "PostFX":
                continue

            # Find TimeSpection effect
            for effect in render_pass.effects:
                if not isinstance(effect, MaterialPostEffect):
                    continue
                if effect.name == "TimeSpection":
                    self._time_effect = effect
                    log.info("[TimeModifierController] Found TimeSpection effect")
                    return

        log.warning("[TimeModifierController] TimeSpection effect not found in PostFX pass")

    def _before_draw(self, shader: "ShaderProgram") -> None:
        """Callback to set uniforms for the post-effect shader."""
        import numpy as np
        print("Before draw TimeModifierController")

        # Set time modifier
        if self._chronosphere_controller is not None:
            time_mult = self._chronosphere_controller.chronosphere.time_multiplier
            shader.set_uniform_float("u_time_modifier", time_mult)

        # Set camera uniforms for depth decoding and world pos reconstruction
        if self._camera is not None:
            shader.set_uniform_float("u_near", self._camera.near)
            shader.set_uniform_float("u_far", self._camera.far)

            # Compute inverse view and projection matrices
            view = self._camera.view_matrix()
            proj = self._camera.projection_matrix()
            inv_view = np.linalg.inv(view).astype(np.float32)
            inv_proj = np.linalg.inv(proj).astype(np.float32)

            print("Inv View Matrix:\n", inv_view)
            print("Inv Projection Matrix:\n", inv_proj)

            shader.set_uniform_matrix4("u_inv_view", inv_view)
            shader.set_uniform_matrix4("u_inv_proj", inv_proj)
        else:
            log.warning("[TimeModifierController] No CameraComponent to set near/far uniforms")

    def on_removed_from_entity(self) -> None:
        """Clean up callback when removed."""
        if self._time_effect is not None:
            self._time_effect.set_before_draw(None)
            self._time_effect = None
        else:
            log.warning("[TimeModifierController] No TimeModifier effect to disconnect")
