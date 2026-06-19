"""
ViewportHintComponent - controls viewport settings from camera entity.

When attached to a camera entity, this component provides hints for viewport
configuration including pipeline selection and layer mask.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from termin.scene import PythonComponent
from termin.inspect import InspectField

if TYPE_CHECKING:
    from termin.render_framework import RenderPipeline
    from termin.visualization.render.framegraph import FramePass


class ViewportHintComponent(PythonComponent):
    """
    Component that provides viewport configuration hints.

    Attach to a camera entity to control viewport settings:
    - Pipeline selection
    - Layer mask (which entity layers to render)

    When a viewport uses a camera with ViewportHintComponent,
    the viewport inspector shows "Controlled by ViewportHint".

    Also provides methods to access pipeline and passes programmatically
    from other scene components.
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
            pass_name: Name of the pass (e.g., "Color", "Tonemap").

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
