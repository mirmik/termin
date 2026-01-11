"""NormalPass - world-space normal rendering pass using C++ implementation."""
from __future__ import annotations

from typing import List, Set, Tuple, TYPE_CHECKING

import numpy as np

from termin._native.render import NormalPass as _NormalPassNative
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, FramebufferHandle
    from termin.visualization.render.framegraph.execute_context import ExecuteContext


class NormalPass(_NormalPassNative):
    """
    Normal rendering pass - writes world-space normals to texture.

    Renders all scene entities with Drawable components, writing
    normals encoded as RGB where (normal * 0.5 + 0.5).

    Uses C++ implementation for core rendering with skinning support.

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
        input_res: str = "empty_normal",
        output_res: str = "normal",
        pass_name: str = "Normal",
        camera_name: str = "",
    ):
        super().__init__(
            input_res=input_res,
            output_res=output_res,
            pass_name=pass_name,
        )
        self.camera_name = camera_name

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "NormalPass":
        return cls(
            pass_name=data.get("pass_name", "Normal"),
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
        """Serialize NormalPass to dict."""
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
        """NormalPass reads input_res and writes output_res inplace."""
        return [(self.input_res, self.output_res)]

    def get_internal_symbols(self) -> List[str]:
        """Return list of entity names (from C++ implementation)."""
        return super().get_internal_symbols()

    def _find_camera_by_name(self, scene, name: str):
        """Find camera component from entity by name."""
        from termin.visualization.core.camera import CameraComponent

        for entity in scene.entities:
            if entity.name == name:
                camera = entity.get_component(CameraComponent)
                if camera is not None:
                    return camera
        return None

    def execute(self, ctx: "ExecuteContext") -> None:
        """Execute normal pass using C++ implementation."""
        scene = ctx.scene
        camera = ctx.camera
        rect = ctx.rect

        # If camera_name is set, use it (overrides passed camera)
        if self.camera_name:
            camera = self._find_camera_by_name(scene, self.camera_name)
            if camera is None:
                return  # Camera not found, skip pass

        if camera is None:
            return  # No camera available

        # Get output FBO and use its size for rendering
        output_fbo = ctx.writes_fbos.get(self.output_res)
        if output_fbo is not None:
            fbo_size = output_fbo.get_size()
            rect = (0, 0, fbo_size.width, fbo_size.height)
            # Update camera aspect ratio to match FBO
            camera.set_aspect(fbo_size.width / max(1, fbo_size.height))

        view = camera.get_view_matrix()
        projection = camera.get_projection_matrix()

        self.execute_with_data(
            graphics=ctx.graphics,
            reads_fbos=ctx.reads_fbos,
            writes_fbos=ctx.writes_fbos,
            rect=rect,
            scene=scene,
            view=view.to_numpy_f32(),
            projection=projection.to_numpy_f32(),
            context_key=ctx.context_key,
            layer_mask=ctx.layer_mask,
        )
