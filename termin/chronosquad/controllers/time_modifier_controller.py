"""TimeModifierController - connects ChronoSphere time to post-process shader."""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin._native import log
from termin.visualization.core.python_component import PythonComponent

if TYPE_CHECKING:
    from .chronosphere_controller import ChronosphereController
    from termin.visualization.render.posteffects.material_effect import MaterialPostEffect
    from termin.visualization.core.shader import ShaderProgram


class TimeModifierController(PythonComponent):
    """
    Connects ChronoSphere time_multiplier to the TimeModifier post-process shader.

    Finds ChronosphereController in the scene and MaterialPostEffect with
    TimeModifier material in the viewport pipeline. Sets the before_draw
    callback to write u_time_modifier uniform.
    """

    def __init__(self, enabled: bool = True):
        super().__init__(enabled=enabled)
        self._chronosphere_controller: ChronosphereController | None = None
        self._time_effect: MaterialPostEffect | None = None
        self._initialized = False

    def start(self) -> None:
        """Find controllers and set up callback."""
        if self._initialized:
            return

        self._find_chronosphere_controller()
        self._find_time_effect()

        if self._time_effect is not None:
            self._time_effect.set_before_draw(self._before_draw)
            log.info("[TimeModifierController] Connected to TimeModifier effect")

        self._initialized = True

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
        from termin.visualization.render.manager import RenderingManager
        from termin.visualization.render.postprocess import PostProcessPass
        from termin.visualization.render.posteffects.material_effect import MaterialPostEffect

        rm = RenderingManager.instance()

        for display in rm.displays:
            for viewport in display.viewports:
                if viewport.scene is not self._scene:
                    continue
                if viewport.pipeline is None:
                    continue

                # Find PostFX pass
                for render_pass in viewport.pipeline.passes:
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
        """Callback to set u_time_modifier uniform."""
        if self._chronosphere_controller is None:
            return

        time_mult = self._chronosphere_controller.chronosphere.time_multiplier
        shader.set_uniform_float("u_time_modifier", time_mult)

    def on_removed_from_entity(self) -> None:
        """Clean up callback when removed."""
        if self._time_effect is not None:
            self._time_effect.set_before_draw(None)
            self._time_effect = None
