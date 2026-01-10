"""MaterialPass - Post-processing pass using a Material asset.

The most universal post-effect - uses any Material for rendering.
Artists can create custom effects via the material system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Set

import numpy as np

from termin.visualization.render.framegraph.passes.post_effect_base import PostEffectPass
from termin.visualization.core.material_handle import MaterialHandle
from termin.editor.inspect_field import InspectField
from termin._native import log

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import (
        GraphicsBackend,
        FramebufferHandle,
        GPUTextureHandle,
    )
    from termin.visualization.core.material import Material


class MaterialPass(PostEffectPass):
    """
    Post-processing pass that uses a Material for rendering.

    The material shader receives:
    - u_input: Main color texture on unit 0
    - u_resolution: vec2 with (width, height)
    - u_time: float with scene time
    - Additional textures from required_resources as u_{resource_name}

    All material uniforms and textures are also bound.
    """

    category = "Effects"

    inspect_fields = {
        "material": InspectField(
            path="_material_handle",
            label="Material",
            kind="material_handle",
        ),
    }

    def __init__(
        self,
        input_res: str = "color",
        output_res: str = "color",
        pass_name: str = "Material",
        material_name: str = "",
    ):
        super().__init__(input_res, output_res, pass_name)
        self._material_handle = MaterialHandle()
        if material_name:
            self._material_handle = MaterialHandle.from_name(material_name)

        # Extra resources to bind (resource_name -> uniform_name)
        self._extra_resources: dict[str, str] = {}

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

    def compute_reads(self) -> Set[str]:
        """Include extra resources in reads."""
        reads = {self.input_res}
        reads.update(self._extra_resources.keys())
        return reads

    def _get_material(self) -> "Material | None":
        """Get material from handle."""
        if self._material_handle:
            return self._material_handle.get_material_or_none()
        return None

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
        shader = phase.shader_programm

        if shader is None:
            self._draw_passthrough(graphics, context_key, input_tex)
            return

        shader.ensure_ready(graphics, context_key)
        shader.use()

        w, h = size
        texture_unit = 0

        # Bind input texture
        input_tex.bind(texture_unit)
        shader.set_uniform_int("u_input", texture_unit)
        texture_unit += 1

        # Bind extra resources
        for resource_name, uniform_name in self._extra_resources.items():
            tex = self.get_texture_from_fbo(reads_fbos, resource_name)
            if tex is not None:
                tex.bind(texture_unit)
                shader.set_uniform_int(uniform_name, texture_unit)
                texture_unit += 1

        # Set standard uniforms
        shader.set_uniform_vec2("u_resolution", np.array([w, h], dtype=np.float32))

        if scene is not None:
            shader.set_uniform_float("u_time", getattr(scene, "time", 0.0))

        # Bind material textures
        for tex_name, tex_handle in phase.textures.items():
            if tex_handle is not None:
                tex_handle.bind(texture_unit)
                shader.set_uniform_int(tex_name, texture_unit)
                texture_unit += 1

        # Set material uniforms
        for uniform_name, uniform_value in phase.uniforms.items():
            self._set_uniform(shader, uniform_name, uniform_value)

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
        input_tex: "GPUTextureHandle",
    ) -> None:
        """Fallback: pass through input unchanged."""
        from termin.visualization.render.framegraph.passes.present import PresentToScreenPass

        shader = PresentToScreenPass._get_shader()
        shader.ensure_ready(graphics, context_key)
        shader.use()
        shader.set_uniform_int("u_tex", 0)
        input_tex.bind(0)
        self.draw_fullscreen_quad(graphics, context_key)
