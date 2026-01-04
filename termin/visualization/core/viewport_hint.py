"""
ViewportHintComponent - controls viewport settings from camera entity.

When attached to a camera entity, this component provides hints for viewport
configuration including pipeline selection and layer mask.
"""

from __future__ import annotations

from termin.visualization.core.python_component import PythonComponent
from termin.editor.inspect_field import InspectField


class ViewportHintComponent(PythonComponent):
    """
    Component that provides viewport configuration hints.

    Attach to a camera entity to control viewport settings:
    - Pipeline selection
    - Layer mask (which entity layers to render)

    When a viewport uses a camera with ViewportHintComponent,
    the viewport inspector shows "Controlled by ViewportHint".
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
