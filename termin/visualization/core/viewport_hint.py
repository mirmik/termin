"""
ViewportHintComponent - controls viewport settings from camera entity.

When attached to a camera entity, this component provides hints for viewport
configuration including pipeline selection and layer mask.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from termin.visualization.core.python_component import PythonComponent
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.render.framegraph.pipeline import RenderPipeline
    from termin.visualization.render.framegraph import FramePass
    from termin.visualization.render.postprocess import PostEffect, PostProcessPass


class ViewportHintComponent(PythonComponent):
    """
    Component that provides viewport configuration hints.

    Attach to a camera entity to control viewport settings:
    - Pipeline selection
    - Layer mask (which entity layers to render)

    When a viewport uses a camera with ViewportHintComponent,
    the viewport inspector shows "Controlled by ViewportHint".

    Also provides methods to access pipeline, passes, and effects
    programmatically from other scene components.
    """

    inspect_fields = {
        "pipeline_name": InspectField(
            path="pipeline_name",
            label="Pipeline",
            kind="pipeline_selector",
        ),
        "layer_mask": InspectField(
            path="layer_mask",
            label="Layers",
            kind="layer_mask",
        ),
    }

    def __init__(self):
        super().__init__()
        self.pipeline_name: str = "Default"
        # All layers enabled by default
        self.layer_mask: int = 0xFFFFFFFFFFFFFFFF

    def get_pipeline(self) -> Optional["RenderPipeline"]:
        """
        Get the RenderPipeline by name from ResourceManager.

        Returns:
            RenderPipeline or None if not found.
        """
        from termin.assets.resources import ResourceManager

        rm = ResourceManager.instance()
        return rm.get_pipeline(self.pipeline_name)

    def get_pass(self, pass_name: str) -> Optional["FramePass"]:
        """
        Get a pass from the pipeline by name.

        Args:
            pass_name: Name of the pass (e.g., "Color", "PostProcess").

        Returns:
            FramePass or None if not found.
        """
        pipeline = self.get_pipeline()
        if pipeline is None:
            return None

        for p in pipeline.passes:
            if p.pass_name == pass_name:
                return p

        return None

    def get_postprocess_pass(self, pass_name: str = "PostProcess") -> Optional["PostProcessPass"]:
        """
        Get a PostProcessPass from the pipeline by name.

        Args:
            pass_name: Name of the PostProcessPass.

        Returns:
            PostProcessPass or None if not found or not a PostProcessPass.
        """
        from termin.visualization.render.postprocess import PostProcessPass

        p = self.get_pass(pass_name)
        if isinstance(p, PostProcessPass):
            return p

        return None

    def get_effect(
        self,
        effect_name: str,
        pass_name: str = "PostProcess",
    ) -> Optional["PostEffect"]:
        """
        Get a post effect by name from a PostProcessPass.

        Args:
            effect_name: Name of the effect.
            pass_name: Name of the PostProcessPass containing the effect.

        Returns:
            PostEffect or None if not found.
        """
        pp = self.get_postprocess_pass(pass_name)
        if pp is None:
            return None

        for eff in pp.effects:
            if eff.name == effect_name:
                return eff

        return None

    def get_effects(self, pass_name: str = "PostProcess") -> list["PostEffect"]:
        """
        Get all effects from a PostProcessPass.

        Args:
            pass_name: Name of the PostProcessPass.

        Returns:
            List of PostEffect objects (empty if pass not found).
        """
        pp = self.get_postprocess_pass(pass_name)
        if pp is None:
            return []

        return list(pp.effects)
