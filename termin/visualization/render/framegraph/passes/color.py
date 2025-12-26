"""ColorPass - main color rendering pass using C++ implementation."""
from __future__ import annotations

from typing import List, Tuple, TYPE_CHECKING

import numpy as np

from termin._native.render import ColorPass as _ColorPassNative
from termin.visualization.render.framegraph.resource_spec import ResourceSpec
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, FramebufferHandle
    from termin.visualization.render.framegraph.resource import ShadowMapArrayResource


# Maximum shadow maps in shader
MAX_SHADOW_MAPS = 4

# Starting texture unit for shadow maps
SHADOW_MAP_TEXTURE_UNIT_START = 8


class ColorPass(_ColorPassNative):
    """
    Main color rendering pass.

    Renders all scene entities with MeshRenderer, filtering material phases
    by phase_mark and sorting by priority.

    Uses C++ implementation for core rendering, with Python wrapper for
    shadow mapping and debug features.
    """

    _DEBUG_FIRST_FRAMES = False
    _DEBUG_DRAW_COUNT = False
    _debug_frame_count = 0

    inspect_fields = {
        "input_res": InspectField(path="input_res", label="Input Resource", kind="string"),
        "output_res": InspectField(path="output_res", label="Output Resource", kind="string"),
        "shadow_res": InspectField(path="shadow_res", label="Shadow Resource", kind="string"),
        "phase_mark": InspectField(path="phase_mark", label="Phase Mark", kind="string"),
        "sort_by_distance": InspectField(path="sort_by_distance", label="Sort by Distance", kind="bool"),
        "clear_depth": InspectField(path="clear_depth", label="Clear Depth", kind="bool"),
    }

    def __init__(
        self,
        input_res: str = "empty",
        output_res: str = "color",
        shadow_res: str | None = "shadow_maps",
        pass_name: str = "Color",
        phase_mark: str | None = None,
        sort_by_distance: bool = False,
        clear_depth: bool = False,
    ):
        if phase_mark is None:
            phase_mark = "opaque"

        # Call C++ constructor
        super().__init__(
            input_res=input_res,
            output_res=output_res,
            phase_mark=phase_mark,
            pass_name=pass_name,
            sort_by_distance=sort_by_distance,
            clear_depth=clear_depth,
        )

        self.shadow_res = shadow_res

        # Update reads to include shadow_res
        if shadow_res is not None:
            self.reads.add(shadow_res)

        # Cache of entity names with MeshRenderer
        self._entity_names: List[str] = []

    def _serialize_params(self) -> dict:
        """Serialize ColorPass parameters."""
        return {
            "input_res": self.input_res,
            "output_res": self.output_res,
            "shadow_res": self.shadow_res,
            "phase_mark": self.phase_mark,
            "sort_by_distance": self.sort_by_distance,
            "clear_depth": self.clear_depth,
        }

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "ColorPass":
        """Create ColorPass from serialized data."""
        return cls(
            input_res=data.get("input_res", "empty"),
            output_res=data.get("output_res", "color"),
            shadow_res=data.get("shadow_res", "shadow_maps"),
            pass_name=data.get("pass_name", "Color"),
            phase_mark=data.get("phase_mark"),
            sort_by_distance=data.get("sort_by_distance", False),
            clear_depth=data.get("clear_depth", False),
        )

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

        # Get ShadowMapArrayResource
        shadow_array = None
        if self.shadow_res is not None:
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
