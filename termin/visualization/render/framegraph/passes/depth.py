"""DepthPass - linear depth rendering pass using C++ implementation."""
from __future__ import annotations

from typing import List, Set, Tuple, TYPE_CHECKING

import numpy as np

from termin._native.render import DepthPass as _DepthPassNative
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, FramebufferHandle


class DepthPass(_DepthPassNative):
    """
    Depth rendering pass - writes linear depth to texture.

    Renders all scene entities with Drawable components, writing
    linear depth normalized to [0, 1] where 0 = near, 1 = far.

    Uses C++ implementation for core rendering with skinning support.
    Output format: R16F for high precision (65536 levels vs 256 for RGBA8).

    When used outside a viewport (camera_name is set), finds camera
    from scene entities by name.
    """

    category = "Render"

    node_inputs = [("input_res", "fbo")]
    node_outputs = [("output_res", "fbo")]
    node_inplace_pairs = [("input_res", "output_res")]

    # Additional inspect fields for node graph (Python-only)
    inspect_fields = {
        "camera_name": InspectField(
            path="camera_name",
            label="Camera",
            kind="string",
            is_inspectable=True,
        ),
    }

    # Node parameter visibility conditions
    node_param_visibility = {
        "camera_name": {"_outside_viewport": True},
    }

    def __init__(
        self,
        input_res: str = "empty_depth",
        output_res: str = "depth",
        pass_name: str = "Depth",
        camera_name: str = "",
    ):
        # Call C++ constructor
        super().__init__(
            input_res=input_res,
            output_res=output_res,
            pass_name=pass_name,
        )
        self.camera_name = camera_name

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "DepthPass":
        return cls(
            pass_name=data.get("pass_name", "Depth"),
            camera_name=data.get("data", {}).get("camera_name", ""),
        )

    @property
    def reads(self) -> Set[str]:
        """Compute read resources dynamically."""
        return {self.input_res}

    @property
    def writes(self) -> Set[str]:
        """Compute write resources dynamically."""
        return {self.output_res}

    def serialize_data(self) -> dict:
        """Serialize fields via InspectRegistry (C++ INSPECT_FIELD) + Python fields."""
        from termin._native.inspect import InspectRegistry
        result = InspectRegistry.instance().serialize_all(self)
        # Add Python-only fields
        if self.camera_name:
            result["camera_name"] = self.camera_name
        return result

    def deserialize_data(self, data: dict) -> None:
        """Deserialize fields via InspectRegistry (C++ INSPECT_FIELD) + Python fields."""
        if not data:
            return
        from termin._native.inspect import InspectRegistry
        InspectRegistry.instance().deserialize_all(self, data)
        # Restore Python-only fields
        self.camera_name = data.get("camera_name", "")

    def serialize(self) -> dict:
        """Serialize DepthPass to dict."""
        result = {
            "type": self.__class__.__name__,
            "pass_name": self.pass_name,
            "enabled": self.enabled,
            "data": self.serialize_data(),
        }
        if self.viewport_name:
            result["viewport_name"] = self.viewport_name
        return result

    def get_inplace_aliases(self) -> List[Tuple[str, str]]:
        """DepthPass reads input_res and writes output_res inplace."""
        return [(self.input_res, self.output_res)]

    def get_internal_symbols(self) -> List[str]:
        """Return list of entity names (from C++ implementation)."""
        return super().get_internal_symbols()

    def _find_camera_by_name(self, scene, name: str):
        """Find camera component from entity by name."""
        for entity in scene.entities:
            if entity.name == name:
                camera = entity.get_component("Camera")
                if camera is not None:
                    return camera
        return None

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
        """Execute depth pass using C++ implementation."""
        # If no camera provided and camera_name is set, find by name
        if camera is None and self.camera_name:
            camera = self._find_camera_by_name(scene, self.camera_name)
            if camera is None:
                return  # No camera found, skip pass

        if camera is None:
            return  # No camera available

        # Get camera matrices
        view = camera.get_view_matrix()
        projection = camera.get_projection_matrix()

        # Get near/far planes
        try:
            near_plane = float(camera.near)
        except AttributeError:
            near_plane = 0.1

        try:
            far_plane = float(camera.far)
        except AttributeError:
            far_plane = 100.0

        # Call C++ execute_with_data
        self.execute_with_data(
            graphics=graphics,
            reads_fbos=reads_fbos,
            writes_fbos=writes_fbos,
            rect=rect,
            entities=list(scene.entities),
            view=view.astype(np.float32),
            projection=projection.astype(np.float32),
            context_key=context_key,
            near_plane=near_plane,
            far_plane=far_plane,
        )
