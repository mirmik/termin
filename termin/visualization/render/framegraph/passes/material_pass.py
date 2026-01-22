"""MaterialPass - Post-processing pass using a Material asset.

The most universal post-effect - uses any Material for rendering.
Artists can create custom effects via the material system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Set, List, Tuple

import numpy as np

from termin.visualization.render.framegraph.passes.post_effect_base import PostEffectPass
from termin._native.render import TcMaterial
from termin.editor.inspect_field import InspectField
from termin._native import log

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import (
        GraphicsBackend,
        FramebufferHandle,
        GPUTextureHandle,
    )
    from termin.visualization.render.framegraph.execute_context import ExecuteContext


class MaterialPass(PostEffectPass):
    """
    Post-processing pass that uses a Material for rendering.

    The material shader receives:
    - u_input: Main color texture on unit 0
    - u_resolution: vec2 with (width, height)
    - u_time: float with scene time
    - Shader texture properties bound from framegraph resources

    Node graph inputs are generated dynamically based on the selected
    material's shader texture properties (@property Texture u_xxx).
    """

    category = "Effects"

    # Inputs are generated dynamically based on material's shader
    # output_res_target is kept for FBO connection
    node_inputs = []
    node_outputs = [("output_res", "fbo")]
    node_inplace_pairs = []

    # Mark this pass as having dynamic inputs based on material
    has_dynamic_inputs = True

    inspect_fields = {
        "material": InspectField(
            path="material_name",
            label="Material",
            kind="tc_material",
        ),
    }

    def __init__(
        self,
        input_res: str = "",
        output_res: str = "color",
        pass_name: str = "Material",
        material_name: str = "",
        **texture_resources,
    ):
        # MaterialPass doesn't use legacy input_res - all textures come from _texture_resources
        super().__init__(input_res, output_res, pass_name)
        self._material = TcMaterial()
        self._material_name = material_name
        if material_name and material_name != "(None)":
            self._material = TcMaterial.from_name(material_name)

        # Extra resources to bind (resource_name -> uniform_name)
        # For programmatic use via add_resource()
        self._extra_resources: dict[str, str] = {}

        # Dynamic texture resources (uniform_name -> resource_name)
        # e.g., {"u_depth_texture": "depth", "u_normal_map": "normal"}
        self._texture_resources: dict[str, str] = {}

        # Callback invoked before drawing (receives material phase for uniform setup)
        # Signature: (phase: MaterialPhase, scene, camera) -> None
        self._before_draw: Callable | None = None

        # Parameters that should NOT be treated as texture resources
        reserved_params = {
            "viewport_name", "pass_name", "enabled", "passthrough",
            "input_res", "output_res", "material_name",
        }

        for key, value in texture_resources.items():
            if not value:
                continue
            # Skip reserved parameters
            if key in reserved_params:
                continue
            # Skip "empty_" resources (unconnected sockets)
            if isinstance(value, str) and value.startswith("empty_"):
                continue
            # Convert socket name to uniform name: depth_texture -> u_depth_texture
            if key.startswith("u_"):
                uniform_name = key
            else:
                uniform_name = f"u_{key}"
            self._texture_resources[uniform_name] = value

    @property
    def material_name(self) -> str:
        """Get material name for serialization."""
        if self._material.is_valid:
            return self._material.name or ""
        return self._material_name or ""

    @material_name.setter
    def material_name(self, value: str) -> None:
        """Set material by name."""
        self._material_name = value
        if value and value != "(None)":
            self._material = TcMaterial.from_name(value)
        else:
            self._material = TcMaterial()

    def add_resource(self, resource_name: str, uniform_name: str | None = None) -> "MaterialPass":
        """
        Add a FrameGraph resource to bind as texture.

        Args:
            resource_name: Name of the FrameGraph resource (e.g., "depth", "id").
            uniform_name: Shader uniform name. Defaults to u_{resource_name}.

        Returns:
            self for chaining.
        """
        if uniform_name is None:
            uniform_name = f"u_{resource_name}"
        self._extra_resources[resource_name] = uniform_name
        return self

    def remove_resource(self, resource_name: str) -> "MaterialPass":
        """Remove a resource binding."""
        self._extra_resources.pop(resource_name, None)
        return self

    def set_texture_resource(self, uniform_name: str, resource_name: str) -> "MaterialPass":
        """
        Set a framegraph resource for a shader texture uniform.

        Args:
            uniform_name: Shader uniform name (e.g., "u_depth_texture").
            resource_name: Framegraph resource name (e.g., "depth").

        Returns:
            self for chaining.
        """
        self._texture_resources[uniform_name] = resource_name
        return self

    @property
    def before_draw(self) -> Callable | None:
        """
        Callback invoked before drawing.

        Signature: (phase: MaterialPhase, scene, camera) -> None

        Use this to set custom uniforms on the material phase before rendering.
        """
        return self._before_draw

    @before_draw.setter
    def before_draw(self, callback: Callable | None) -> None:
        """Set before_draw callback."""
        self._before_draw = callback

    @classmethod
    def get_texture_inputs_for_material(cls, material_name: str) -> List[Tuple[str, str]]:
        """
        Get list of texture inputs for a material's shader.

        Args:
            material_name: Name of the material.

        Returns:
            List of (input_name, socket_type) tuples for node inputs.
            input_name is derived from uniform name (u_depth -> depth).
            Includes u_input as "input" if shader uses it.
        """
        if not material_name or material_name == "(None)":
            return []

        from termin.visualization.core.resources import ResourceManager

        rm = ResourceManager.instance()
        material = rm.get_material(material_name)
        if material is None:
            log.warn(f"[get_texture_inputs_for_material] material '{material_name}' not found")
            return []

        shader_name = material.shader_name
        if not shader_name:
            log.warn(f"[get_texture_inputs_for_material] material '{material_name}' has no shader_name")
            return []

        program = rm.get_shader(shader_name)
        if program is None or not program.phases:
            log.warn(f"[get_texture_inputs_for_material] shader '{shader_name}' not found or has no phases")
            return []

        # Collect texture uniforms from first phase
        inputs = []
        for prop in program.phases[0].uniforms:
            if prop.property_type == "Texture":
                uniform_name = prop.name
                # Convert uniform name to input name: u_depth_texture -> depth_texture
                # u_input -> input (for standard post-effect input)
                if uniform_name.startswith("u_"):
                    input_name = uniform_name[2:]
                else:
                    input_name = uniform_name
                inputs.append((input_name, "fbo"))

        return inputs

    def get_shader_texture_uniforms(self) -> List[str]:
        """
        Get list of texture uniform names from the material's shader.

        Returns:
            List of uniform names with property_type == "Texture".
        """
        material = self._get_material()
        if material is None or not material.phases:
            return []

        # Get shader asset to access uniform properties
        from termin.visualization.core.resources import ResourceManager

        rm = ResourceManager.instance()
        shader_name = material.shader_name
        if not shader_name:
            return []

        program = rm.get_shader(shader_name)
        if program is None or not program.phases:
            return []

        # Collect texture uniforms from first phase
        texture_uniforms = []
        for prop in program.phases[0].uniforms:
            if prop.property_type == "Texture":
                texture_uniforms.append(prop.name)

        return texture_uniforms

    def compute_reads(self) -> Set[str]:
        """Include all texture resources in reads."""
        reads: Set[str] = set()

        # Add extra resources (from add_resource() API)
        reads.update(self._extra_resources.keys())

        # Add texture resources connected via node graph
        for resource_name in self._texture_resources.values():
            if resource_name:
                reads.add(resource_name)

        # Fallback: if no texture resources, use legacy input_res
        if not reads and self.input_res:
            reads.add(self.input_res)

        return reads

    def serialize_data(self) -> dict:
        """Serialize MaterialPass-specific fields."""
        result = {
            "material_name": self.material_name,
        }
        # Save texture resources if any (filter out bad entries)
        if self._texture_resources:
            clean_resources = {}
            for uniform_name, resource_name in self._texture_resources.items():
                # Skip viewport_name that might have leaked in
                if "viewport" in uniform_name.lower():
                    continue
                # Skip empty resources
                if not resource_name or resource_name.startswith("empty_"):
                    continue
                clean_resources[uniform_name] = resource_name
            if clean_resources:
                result["texture_resources"] = clean_resources
        if self._extra_resources:
            result["extra_resources"] = dict(self._extra_resources)
        return result

    def deserialize_data(self, data: dict) -> None:
        """Deserialize MaterialPass-specific fields."""
        if not data:
            return
        self.material_name = data.get("material_name", "")
        # Restore texture resources (filter out bad entries)
        texture_resources = data.get("texture_resources", {})
        self._texture_resources = {}
        for uniform_name, resource_name in texture_resources.items():
            # Skip viewport_name that might have leaked in
            if "viewport" in uniform_name.lower():
                continue
            # Skip empty resources
            if not resource_name or resource_name.startswith("empty_"):
                continue
            self._texture_resources[uniform_name] = resource_name
        extra_resources = data.get("extra_resources", {})
        self._extra_resources = dict(extra_resources)

    def serialize(self) -> dict:
        """Serialize MaterialPass to dict."""
        result = {
            "type": self.__class__.__name__,
            "pass_name": self.pass_name,
            "enabled": self.enabled,
            "output_res": self.output_res,
            "data": self.serialize_data(),
        }
        if self.viewport_name:
            result["viewport_name"] = self.viewport_name
        return result

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "MaterialPass":
        """Create instance from serialized data."""
        return cls(
            pass_name=data.get("pass_name", "Material"),
            output_res=data.get("output_res", "color"),
        )

    def _get_material(self) -> "TcMaterial | None":
        """Get material."""
        return self._material if self._material.is_valid else None

    def execute(self, ctx: "ExecuteContext") -> None:
        """Execute the material pass.

        Unlike base PostEffectPass, MaterialPass doesn't require input_res.
        All textures come from _texture_resources bound via node graph.
        """
        if not self.enabled:
            return

        output_fbo = ctx.writes_fbos.get(self.output_res)

        # Get output size
        if output_fbo is not None:
            w, h = output_fbo.get_size()
        else:
            _, _, w, h = ctx.rect

        # Bind output FBO
        ctx.graphics.bind_framebuffer(output_fbo)
        ctx.graphics.set_viewport(0, 0, w, h)

        # Standard post-effect state
        ctx.graphics.set_depth_test(False)
        ctx.graphics.set_depth_mask(False)
        ctx.graphics.set_blend(False)

        # Apply the effect (input_tex=None, all textures from reads_fbos)
        self.apply(
            graphics=ctx.graphics,
            input_tex=None,
            output_fbo=output_fbo,
            size=(w, h),
            context_key=ctx.context_key,
            reads_fbos=ctx.reads_fbos,
            scene=ctx.scene,
            camera=ctx.camera,
        )

        # Restore state
        ctx.graphics.set_depth_test(True)
        ctx.graphics.set_depth_mask(True)

    def apply(
        self,
        graphics: "GraphicsBackend",
        input_tex: "GPUTextureHandle",
        output_fbo: "FramebufferHandle | None",
        size: tuple[int, int],
        context_key: int,
        reads_fbos: dict[str, "FramebufferHandle | None"],
        scene,
        camera,
    ) -> None:
        """Apply material-based effect."""
        material = self._get_material()

        if material is None or not material.phases:
            # Passthrough - just copy input to output
            self._draw_passthrough(graphics, context_key, input_tex)
            return

        phase = material.phases[0]
        shader = phase.shader

        if not shader.is_valid:
            self._draw_passthrough(graphics, context_key, input_tex)
            return

        shader.ensure_ready()
        shader.use()

        w, h = size
        texture_unit = 0

        # Track which uniforms we've bound from framegraph resources
        bound_uniforms: set[str] = set()

        # Bind input texture to u_input if shader uses it
        # (input_tex comes from input_res connection, mapped to "input" socket -> "u_input" uniform)
        if "u_input" in self._texture_resources:
            # u_input is connected via node graph - will be bound below
            pass
        elif input_tex is not None:
            # Legacy: bind input_tex directly if available
            input_tex.bind(texture_unit)
            shader.set_uniform_int("u_input", texture_unit)
            texture_unit += 1
            bound_uniforms.add("u_input")

        # Bind extra resources (explicitly configured via add_resource())
        for resource_name, uniform_name in self._extra_resources.items():
            tex = self.get_texture_from_fbo(reads_fbos, resource_name)
            if tex is not None:
                tex.bind(texture_unit)
                shader.set_uniform_int(uniform_name, texture_unit)
                texture_unit += 1
                bound_uniforms.add(uniform_name)

        # Bind texture resources connected via node graph
        # _texture_resources maps uniform_name -> resource_name
        for uniform_name, resource_name in self._texture_resources.items():
            if not resource_name:
                continue
            tex = self.get_texture_from_fbo(reads_fbos, resource_name)
            if tex is not None:
                tex.bind(texture_unit)
                shader.set_uniform_int(uniform_name, texture_unit)
                texture_unit += 1
                bound_uniforms.add(uniform_name)

        # Set standard uniforms
        shader.set_uniform_vec2("u_resolution", np.array([w, h], dtype=np.float32))

        # if scene is not None:
        #     shader.set_uniform_float("u_time", getattr(scene, "time", 0.0))

        # Bind material textures (skip those already bound from framegraph)
        for tex_name, tex_handle in phase.textures.items():
            # Skip if already bound from framegraph resource
            if tex_name in bound_uniforms:
                continue
            if tex_handle is not None:
                # TcTexture uses bind_gpu(unit) instead of bind(graphics, unit, context_key)
                tex_handle.upload_gpu()
                tex_handle.bind_gpu(texture_unit)
                shader.set_uniform_int(tex_name, texture_unit)
                texture_unit += 1

        # Set material uniforms
        for uniform_name, uniform_value in phase.uniforms.items():
            self._set_uniform(shader, uniform_name, uniform_value)

        # Call before_draw callback for custom uniform setup
        if self._before_draw is not None:
            self._before_draw(shader)

        # Draw
        self.draw_fullscreen_quad(graphics, context_key)

    def _set_uniform(self, shader, name: str, value) -> None:
        """Set uniform based on value type."""
        from termin.geombase import Vec3, Vec4

        if isinstance(value, (int, bool)):
            shader.set_uniform_int(name, int(value))
        elif isinstance(value, float):
            shader.set_uniform_float(name, value)
        elif isinstance(value, Vec3):
            shader.set_uniform_vec3(name, np.array([value.x, value.y, value.z], dtype=np.float32))
        elif isinstance(value, Vec4):
            shader.set_uniform_vec4(name, np.array([value.x, value.y, value.z, value.w], dtype=np.float32))
        elif isinstance(value, np.ndarray):
            if value.size == 2:
                shader.set_uniform_vec2(name, value.astype(np.float32))
            elif value.size == 3:
                shader.set_uniform_vec3(name, value.astype(np.float32))
            elif value.size == 4:
                shader.set_uniform_vec4(name, value.astype(np.float32))
            elif value.size == 16:
                shader.set_uniform_matrix4(name, value.astype(np.float32))
        elif isinstance(value, (list, tuple)):
            arr = np.array(value, dtype=np.float32)
            self._set_uniform(shader, name, arr)

    def _draw_passthrough(
        self,
        graphics: "GraphicsBackend",
        context_key: int,
        input_tex: "GPUTextureHandle | None",
    ) -> None:
        """Fallback: pass through input unchanged."""
        if input_tex is None:
            return

        from termin.visualization.render.framegraph.passes.present import PresentToScreenPass

        shader = PresentToScreenPass._get_shader()
        shader.ensure_ready()
        shader.use()
        shader.set_uniform_int("u_tex", 0)
        input_tex.bind(0)
        self.draw_fullscreen_quad(graphics, context_key)

    def destroy(self) -> None:
        """Clean up resources and callbacks."""
        self._before_draw = None
        self._material = TcMaterial()
        self._extra_resources.clear()
        self._texture_resources.clear()
