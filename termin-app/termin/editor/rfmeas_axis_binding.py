"""RfmeasAxisBinding component — stores rfmeas axis name on an entity."""

from __future__ import annotations

from termin.scene.python_component import PythonComponent
from termin.inspect import InspectField


class RfmeasAxisBinding(PythonComponent):
    """Binds an rfmeas positioner axis name to this entity."""

    inspect_fields = {
        "axis_name": InspectField(
            path="axis_name",
            label="Axis Name",
            kind="string",
        ),
    }

    def __init__(self, enabled: bool = True, display_name: str = ""):
        self.axis_name: str = ""
        super().__init__(enabled=enabled, display_name=display_name)
