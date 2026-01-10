"""ColorPass - main color rendering pass using C++ implementation."""
from __future__ import annotations

from typing import List, Set, Tuple, TYPE_CHECKING

import numpy as np

from termin._native.render import ColorPass as _ColorPassNative
from termin.visualization.render.framegraph.resource_spec import ResourceSpec

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, FramebufferHandle
    from termin.visualization.render.framegraph.resource import ShadowMapArrayResource


# Maximum shadow maps in shader (4 lights * 4 cascades)
MAX_SHADOW_MAPS = 16

# Starting texture unit for shadow maps
SHADOW_MAP_TEXTURE_UNIT_START = 8


class ColorPass(_ColorPassNative):
    """
    Main color rendering pass.

    Renders all scene entities with MeshRenderer, filtering material phases
    by phase_mark and sorting by priority.

    Uses C++ implementation for core rendering, with Python wrapper for
    shadow mapping and debug features.

    Fields are registered via INSPECT_FIELD macros in C++ (color_pass.hpp).
    """

    category = "Render"

    node_inputs = [
        ("input_res", "fbo"),
        ("shadow_res", "shadow"),
    ]
    node_outputs = [
        ("output_res", "fbo"),
    ]
    node_inplace_pairs = [("input_res", "output_res")]

    def __init__(
        self,
        input_res: str = "empty",
        output_res: str = "color",
        shadow_res: str | None = "shadow_maps",
        pass_name: str = "Color",
        phase_mark: str | None = None,
        sort_mode: str = "none",  # "none", "near_to_far", "far_to_near"
        clear_depth: bool = False,
    ):
        if phase_mark is None:
            phase_mark = "opaque"

        # Call C++ constructor (shadow_res is now handled in C++)
        super().__init__(
            input_res=input_res,
            output_res=output_res,
            shadow_res=shadow_res if shadow_res is not None else "",
            phase_mark=phase_mark,
            pass_name=pass_name,
            sort_mode=sort_mode,
            clear_depth=clear_depth,
        )

        # Cache of entity names with MeshRenderer
        self._entity_names: List[str] = []

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "ColorPass":
        return cls(pass_name=data.get("pass_name", "Color"))

    @property
    def reads(self) -> Set[str]:
        """Compute read resources dynamically (overrides C++ member)."""
        result = {self.input_res}
        if self.shadow_res:
            result.add(self.shadow_res)
        return result

    @property
    def writes(self) -> Set[str]:
        """Compute write resources dynamically (overrides C++ member)."""
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
        """Serialize ColorPass to dict."""
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
        """ColorPass reads input_res and writes output_res inplace."""
        return [(self.input_res, self.output_res)]

    def get_resource_specs(self) -> List[ResourceSpec]:
        """Declare input resource requirements."""
        return [
            ResourceSpec(
                resource=self.input_res,
                clear_color=(0.2, 0.2, 0.2, 1.0),
                clear_depth=1.0,
            )
        ]

    def get_internal_symbols(self) -> List[str]:
        """Return list of entity names with MeshRenderer."""
        return list(self._entity_names)

    def _bind_shadow_maps(
        self,
        graphics: "GraphicsBackend",
        shadow_array: "ShadowMapArrayResource | None",
    ) -> None:
        """Bind shadow map textures to texture units."""
        from termin.visualization.render.texture import get_dummy_shadow_texture

        bound_count = 0
        if shadow_array is not None:
            for i, entry in enumerate(shadow_array):
                if i >= MAX_SHADOW_MAPS:
                    break
                unit = SHADOW_MAP_TEXTURE_UNIT_START + i
                texture = entry.texture()
                texture.bind(unit)
                bound_count += 1

        # Bind dummy texture to remaining slots (for AMD)
        dummy = get_dummy_shadow_texture()
        for i in range(bound_count, MAX_SHADOW_MAPS):
            unit = SHADOW_MAP_TEXTURE_UNIT_START + i
            dummy.bind(unit)

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
        """Execute color pass using C++ implementation."""
        if lights is not None:
            scene.lights = lights

        # Get ShadowMapArrayResource (shadow_res is "" if disabled)
        shadow_array = None
        if self.shadow_res:
            shadow_array = reads_fbos.get(self.shadow_res)
            from termin.visualization.render.framegraph.resource import ShadowMapArrayResource
            if not isinstance(shadow_array, ShadowMapArrayResource):
                shadow_array = None

        # Bind shadow maps to texture units
        self._bind_shadow_maps(graphics, shadow_array)

        # Get camera matrices
        view = camera.get_view_matrix()
        projection = camera.get_projection_matrix()

        # Get camera position
        if camera.entity is not None:
            cam_pos = camera.entity.transform.global_pose().lin
        else:
            cam_pos = np.array([0.0, 0.0, 0.0])

        # Convert camera position to numpy array
        cam_pos_arr = np.array([cam_pos.x, cam_pos.y, cam_pos.z], dtype=np.float64)

        # Get ambient (may be Vec3 or numpy array)
        ac = scene.ambient_color
        if hasattr(ac, 'x'):
            ambient_color = np.array([ac.x, ac.y, ac.z], dtype=np.float64)
        else:
            ambient_color = np.asarray(ac, dtype=np.float64)
        ambient_intensity = float(scene.ambient_intensity)

        # Call C++ execute_with_data
        # Debugger window and depth callback are already set on C++ object
        self.execute_with_data(
            graphics=graphics,
            reads_fbos=reads_fbos,
            writes_fbos=writes_fbos,
            rect=rect,
            entities=list(scene.entities),
            view=view.astype(np.float32),
            projection=projection.astype(np.float32),
            camera_position=cam_pos_arr,
            context_key=context_key,
            lights=list(scene.lights) if scene.lights else [],
            ambient_color=ambient_color,
            ambient_intensity=ambient_intensity,
            shadow_array=shadow_array,
            shadow_settings=scene.shadow_settings,
        )
