"""ColorPass - main color rendering pass using C++ implementation."""
from __future__ import annotations

from typing import List, Set, Tuple, TYPE_CHECKING

import numpy as np

from termin._native.render import ColorPass as _ColorPassNative
from termin.visualization.render.framegraph.resource_spec import ResourceSpec
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, FramebufferHandle
    from termin.visualization.render.framegraph.resource import ShadowMapArrayResource
    from termin.visualization.render.framegraph.execute_context import ExecuteContext


# Maximum shadow maps in shader (4 lights * 4 cascades)
MAX_SHADOW_MAPS = 16

# Starting texture unit for shadow maps
SHADOW_MAP_TEXTURE_UNIT_START = 8

# Starting texture unit for extra textures (after shadow maps)
EXTRA_TEXTURE_UNIT_START = 24


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

    # Mark as having dynamic inputs (for extra texture inputs)
    has_dynamic_inputs = True

    # Static inputs (always present)
    node_inputs = [
        ("input_res", "fbo"),
        ("shadow_res", "shadow"),
    ]
    node_outputs = [
        ("output_res", "fbo"),
    ]
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
        input_res: str = "empty",
        output_res: str = "color",
        shadow_res: str | None = "shadow_maps",
        pass_name: str = "Color",
        phase_mark: str | None = None,
        sort_mode: str = "none",  # "none", "near_to_far", "far_to_near"
        clear_depth: bool = False,
        camera_name: str = "",
        **extra_textures,
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
        self.camera_name = camera_name

        # Extra texture resources: uniform_name -> resource_name
        # These will be bound before rendering and passed to shaders
        self._extra_textures: dict[str, str] = {}
        for key, value in extra_textures.items():
            if value and not value.startswith("empty_"):
                # Ensure u_ prefix for uniform name
                uniform_name = f"u_{key}" if not key.startswith("u_") else key
                self._extra_textures[uniform_name] = value
        self._cached_camera_name: str | None = None
        self._cached_camera_component = None


    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "ColorPass":
        return cls(
            pass_name=data.get("pass_name", "Color"),
            camera_name=data.get("data", {}).get("camera_name", ""),
        )

    @property
    def reads(self) -> Set[str]:
        """Compute read resources dynamically (overrides C++ member)."""
        result = {self.input_res}
        if self.shadow_res:
            result.add(self.shadow_res)
        # Add extra texture resources
        for resource_name in self._extra_textures.values():
            result.add(resource_name)
        return result

    @property
    def writes(self) -> Set[str]:
        """Compute write resources dynamically (overrides C++ member)."""
        return {self.output_res}

    def serialize_data(self) -> dict:
        """Serialize fields via InspectRegistry (C++ INSPECT_FIELD) + Python fields."""
        from termin._native.inspect import InspectRegistry
        result = InspectRegistry.instance().serialize_all(self)
        # Add Python-only fields
        if self.camera_name:
            result["camera_name"] = self.camera_name
        # Add extra textures
        if self._extra_textures:
            result["extra_textures"] = self._extra_textures.copy()
        return result

    def deserialize_data(self, data: dict) -> None:
        """Deserialize fields via InspectRegistry (C++ INSPECT_FIELD) + Python fields."""
        if not data:
            return
        from termin._native.inspect import InspectRegistry
        InspectRegistry.instance().deserialize_all(self, data)
        # Restore Python-only fields
        self.camera_name = data.get("camera_name", "")
        # Restore extra textures
        self._extra_textures = data.get("extra_textures", {})

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
        """Return list of entity names (from C++ implementation)."""
        return super().get_internal_symbols()

    def _find_camera_by_name(self, scene, name: str):
        """Find camera component from entity by name."""
        from termin.visualization.core.camera import CameraComponent

        if self._cached_camera_name == name and self._cached_camera_component is not None:
            return self._cached_camera_component

        for entity in scene.entities:
            if entity.name == name:
                camera = entity.get_component(CameraComponent)
                if camera is not None:
                    self._cached_camera_name = name
                    self._cached_camera_component = camera
                    return camera
        return None

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

    def _bind_extra_textures(
        self,
        reads_fbos: dict[str, "FramebufferHandle | None"],
    ) -> None:
        """Bind extra textures to texture units and set C++ uniforms map."""
        from termin._native import log

        # Clear previous frame's uniforms
        self.clear_extra_textures()

        for i, (uniform_name, resource_name) in enumerate(self._extra_textures.items()):
            fbo = reads_fbos.get(resource_name)
            if fbo is None:
                log.warn(f"[ColorPass:{self.pass_name}] FBO not found for resource: {resource_name}")
                continue

            # Get color texture from FBO
            try:
                tex = fbo.color_texture()
            except AttributeError as e:
                log.warn(f"[ColorPass:{self.pass_name}] No color_texture on FBO {resource_name}: {e}")
                continue

            # Bind to texture unit
            unit = EXTRA_TEXTURE_UNIT_START + i
            tex.bind(unit)

            # Register uniform->unit mapping for C++ to use
            self.set_extra_texture_uniform(uniform_name, unit)

    def execute(self, ctx: "ExecuteContext") -> None:
        """Execute color pass using C++ implementation."""
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

        if ctx.lights is not None:
            scene.lights = ctx.lights

        # Get ShadowMapArrayResource (shadow_res is "" if disabled)
        shadow_array = None
        if self.shadow_res:
            shadow_array = ctx.reads_fbos.get(self.shadow_res)
            from termin.visualization.render.framegraph.resource import ShadowMapArrayResource
            if not isinstance(shadow_array, ShadowMapArrayResource):
                shadow_array = None

        # Bind shadow maps to texture units
        self._bind_shadow_maps(ctx.graphics, shadow_array)

        # Bind extra textures (if any)
        if self._extra_textures:
            self._bind_extra_textures(ctx.reads_fbos)

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
            graphics=ctx.graphics,
            reads_fbos=ctx.reads_fbos,
            writes_fbos=ctx.writes_fbos,
            rect=rect,
            scene=scene,
            view=view.to_numpy_f32(),
            projection=projection.to_numpy_f32(),
            camera_position=cam_pos_arr,
            context_key=ctx.context_key,
            lights=list(scene.lights) if scene.lights else [],
            ambient_color=ambient_color,
            ambient_intensity=ambient_intensity,
            shadow_array=shadow_array,
            shadow_settings=scene.shadow_settings,
            layer_mask=ctx.layer_mask,
        )
