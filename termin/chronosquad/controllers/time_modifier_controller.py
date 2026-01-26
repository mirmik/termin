"""TimeModifierController - connects ChronoSphere time to post-process shader."""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin._native import log
from termin.visualization.core.python_component import PythonComponent
from termin.visualization.render.manager import RenderingManager

if TYPE_CHECKING:
    from .chronosphere_controller import ChronosphereController
    from termin.visualization.render.posteffects.material_effect import MaterialPostEffect
    from termin._native.render import TcShader
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
        self._time_effect_pass: MaterialPass | None = None
        self._initialized = False

    def start(self) -> None:
        """Find controllers and set up callback."""
        if self._initialized:
            return

        self._find_camera()
        self._find_chronosphere_controller()
        self._find_time_effect()
        self._find_time_effect_pass()

        if self._time_effect is not None:
            self._time_effect.set_before_draw(self._before_draw)
            log.info("[TimeModifierController] Connected to TimeModifier effect")
        else:
            log.warning("[TimeModifierController] TimeModifier effect not found; cannot connect")

        if self._time_effect_pass is not None:
            self._time_effect_pass.before_draw = self._before_draw
            log.info("[TimeModifierController] Found MaterialPass for TimeModifier effect")
        else:
            log.warning("[TimeModifierController] MaterialPass for TimeModifier effect not found")

        self._initialized = True

    def _find_camera(self) -> None:
        """Find CameraComponent on this entity."""
        from termin.visualization.core.camera import CameraComponent

        self._camera = self.entity.get_component(CameraComponent)
        if self._camera is None:
            log.warning("[TimeModifierController] CameraComponent not found on entity")

    def _find_chronosphere_controller(self) -> None:
        """Find ChronosphereController in scene."""
        from .chronosphere_controller import ChronosphereController

        if self.scene is None:
            return

        for entity in self.scene.entities:
            comp = entity.get_component(ChronosphereController)
            if comp is not None:
                self._chronosphere_controller = comp
                log.info(f"[TimeModifierController] Found ChronosphereController on '{entity.name}'")
                return

        log.warning("[TimeModifierController] ChronosphereController not found in scene")

    def _find_time_effect(self) -> None:
        # """Find MaterialPostEffect named 'TimeSpection' in 'PostFX' pass."""
        # from termin.visualization.render.postprocess import PostProcessPass
        # from termin.visualization.render.posteffects.material_effect import MaterialPostEffect

        # if self._camera is None:
        #     log.warning("[TimeModifierController] No camera")
        #     return

        # # Get live pipeline from camera's viewport
        # viewport = self._camera.viewport
        # if viewport is None:
        #     log.warning("[TimeModifierController] Camera has no viewport")
        #     return

        # pipeline = viewport.pipeline
        # if pipeline is None:
        #     log.warning("[TimeModifierController] Viewport has no pipeline")
        #     return

        # # Find PostFX pass
        # for render_pass in pipeline.passes:
        #     if not isinstance(render_pass, PostProcessPass):
        #         continue
        #     if render_pass.pass_name != "PostFX":
        #         continue

        #     # Find TimeSpection effect
        #     for effect in render_pass.effects:
        #         if not isinstance(effect, MaterialPostEffect):
        #             continue
        #         if effect.name == "TimeSpection":
        #             self._time_effect = effect.to_python()
        #             log.info("[TimeModifierController] Found TimeSpection effect")
        #             return

        # log.warning("[TimeModifierController] TimeSpection effect not found in PostFX pass")
        pass

    def _find_time_effect_pass(self) -> None:
        rm = RenderingManager.instance()
        if rm is None:
            log.error("[TimeModifierController] No RenderingManager instance")
            return
        
        pipeline = rm.get_scene_pipeline("TestScenePipeline")
        if pipeline is None:
            log.error("[TimeModifierController] No TestScenePipeline found")
            return

        render_pass = pipeline.get_pass_by_name("TimeSpection")
        if render_pass is None:
            log.warning("[TimeModifierController] No TimeSpection pass found in pipeline")
            return

        self._time_effect_pass = render_pass.to_python()

    def _before_draw(self, shader: "TcShader") -> None:
        """Callback to set uniforms for the post-effect shader."""
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

            shader.set_uniform_mat4("u_inv_view", view.inverse(), False)
            shader.set_uniform_mat4("u_inv_proj", proj.inverse(), False)

            shader.set_uniform_float("u_grid_scale", 1.0)
            shader.set_uniform_float("u_grid_line_width", 0.03)
            shader.set_uniform_float("u_grid_intensity", 0.3)

        else:
            log.warning("[TimeModifierController] No CameraComponent to set near/far uniforms")

    def on_removed_from_entity(self) -> None:
        """Clean up callback when removed."""
        if self._time_effect is not None:
            self._time_effect.set_before_draw(None)
            self._time_effect = None
        else:
            log.warning("[TimeModifierController] No TimeModifier effect to disconnect")
