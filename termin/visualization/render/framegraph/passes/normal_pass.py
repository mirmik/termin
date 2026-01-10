"""NormalPass - world-space normal rendering pass using C++ implementation."""
from __future__ import annotations

from typing import List, Set, Tuple, TYPE_CHECKING

import numpy as np

from termin._native.render import NormalPass as _NormalPassNative

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, FramebufferHandle


class NormalPass(_NormalPassNative):
    """
    Normal rendering pass - writes world-space normals to texture.

    Renders all scene entities with Drawable components, writing
    normals encoded as RGB where (normal * 0.5 + 0.5).

    Uses C++ implementation for core rendering with skinning support.
    """

    category = "Render"

    node_inputs = [("input_res", "fbo")]
    node_outputs = [("output_res", "fbo")]
    node_inplace_pairs = [("input_res", "output_res")]

    def __init__(
        self,
        input_res: str = "empty_normal",
        output_res: str = "normal",
        pass_name: str = "Normal",
    ):
        super().__init__(
            input_res=input_res,
            output_res=output_res,
            pass_name=pass_name,
        )

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "NormalPass":
        return cls(pass_name=data.get("pass_name", "Normal"))

    @property
    def reads(self) -> Set[str]:
        """Compute read resources dynamically."""
        return {self.input_res}

    @property
    def writes(self) -> Set[str]:
        """Compute write resources dynamically."""
        return {self.output_res}

    def serialize_data(self) -> dict:
        """Serialize fields via InspectRegistry (C++ INSPECT_FIELD)."""
        from termin._native.inspect import InspectRegistry
        return InspectRegistry.instance().serialize_all(self)

    def deserialize_data(self, data: dict) -> None:
        """Deserialize fields via InspectRegistry (C++ INSPECT_FIELD)."""
        if not data:
            return
        from termin._native.inspect import InspectRegistry
        InspectRegistry.instance().deserialize_all(self, data)

    def serialize(self) -> dict:
        """Serialize NormalPass to dict."""
        return {
            "type": self.__class__.__name__,
            "pass_name": self.pass_name,
            "enabled": self.enabled,
            "data": self.serialize_data(),
        }

    def get_inplace_aliases(self) -> List[Tuple[str, str]]:
        """NormalPass reads input_res and writes output_res inplace."""
        return [(self.input_res, self.output_res)]

    def get_internal_symbols(self) -> List[str]:
        """Return list of entity names (from C++ implementation)."""
        return super().get_internal_symbols()

    def execute(
        self,
        graphics: "GraphicsBackend",
        reads_fbos: dict[str, "FramebufferHandle | None"],
        writes_fbos: dict[str, "FramebufferHandle | None"],
        rect: tuple[int, int, int, int],
        scene,
        camera,
        context_key: int,
        lights=None,
        canvas=None,
    ):
        """Execute normal pass using C++ implementation."""
        view = camera.get_view_matrix()
        projection = camera.get_projection_matrix()

        self.execute_with_data(
            graphics=graphics,
            reads_fbos=reads_fbos,
            writes_fbos=writes_fbos,
            rect=rect,
            entities=list(scene.entities),
            view=view.astype(np.float32),
            projection=projection.astype(np.float32),
            context_key=context_key,
        )
