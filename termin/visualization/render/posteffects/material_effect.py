"""MaterialPostEffect - Post effect that uses a Material for rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional, Set

from termin.visualization.render.postprocess import PostEffect
from termin.visualization.core.material_handle import MaterialHandle
from termin.editor.inspect_field import InspectField
from termin._native import log

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, GPUTextureHandle
    from termin.visualization.core.material import Material
    from termin._native.render import TcShader

# Callback type: (shader) -> None
BeforeDrawCallback = Callable[["TcShader"], None]


class MaterialPostEffect(PostEffect):
    """
    Post effect that uses a Material asset for rendering.

    This allows artists to create post effects using the material system,
    with custom shaders and parameters editable in the inspector.

    The material shader receives:
    - u_input_tex: Main color texture (from previous pass) on unit 0
    - u_depth: Depth texture (if required_depth=True)
    - u_resolution: vec2 with (width, height)
    - Extra resources specified via add_resource() as their uniform names

    Additional textures and uniforms come from the material itself.
    """

    name = "material"

    inspect_fields = {
        "material": InspectField(
            path="_material_handle",
            label="Material",
            kind="material_handle",
        ),
        "required_depth": InspectField(
            path="_required_depth",
            label="Require Depth",
            kind="bool",
        ),
        "extra_resources": InspectField(
            path="extra_resources_str",
            label="Extra Resources (res:uni, ...)",
            kind="string",
        ),
    }

    def __init__(
        self,
        material_path: str = "",
        required_depth: bool = False,
    ):
        """
        Args:
            material_path: Path to .material file (relative to project).
            required_depth: Whether this effect needs the depth buffer.
        """
        self._material_handle = MaterialHandle()
        if material_path:
            self._material_handle = MaterialHandle.from_name(material_path)
        self._required_depth = required_depth
        self._before_draw: Optional[BeforeDrawCallback] = None
        # Map: resource_name -> uniform_name
        self._extra_resources: dict[str, str] = {}

    @property
    def extra_resources_str(self) -> str:
        """Get extra resources as string for inspector."""
        if not self._extra_resources:
            return ""
        return ", ".join(f"{res}:{uni}" for res, uni in self._extra_resources.items())

    @extra_resources_str.setter
    def extra_resources_str(self, value: str) -> None:
        """Set extra resources from string (format: 'resource:uniform, ...')."""
        self._extra_resources.clear()
        if not value or not value.strip():
            return
        for pair in value.split(","):
            pair = pair.strip()
            if ":" in pair:
                res, uni = pair.split(":", 1)
                res = res.strip()
                uni = uni.strip()
                if res and uni:
                    self._extra_resources[res] = uni

    def set_before_draw(self, callback: Optional[BeforeDrawCallback]) -> None:
        """
        Set callback to be called before drawing.

        The callback receives the shader program and can set additional uniforms.
        Called after the shader is bound but before drawing the quad.

        Args:
            callback: Callable[[TcShader], None] or None to clear.
        """
        self._before_draw = callback

    def clear_callbacks(self) -> None:
        """Clear before_draw callback."""
        self._before_draw = None

    def add_resource(self, resource_name: str, uniform_name: str) -> "MaterialPostEffect":
        """
        Add a FrameGraph resource to be bound as a texture uniform.

        Args:
            resource_name: Name of the FrameGraph resource (e.g. "id", "depth").
            uniform_name: Name of the sampler uniform in the shader (e.g. "u_id").

        Returns:
            self for chaining.

        Example:
            effect.add_resource("id", "u_id").add_resource("depth", "u_depth")
        """
        self._extra_resources[resource_name] = uniform_name
        return self

    def remove_resource(self, resource_name: str) -> "MaterialPostEffect":
        """
        Remove a previously added resource.

        Args:
            resource_name: Name of the FrameGraph resource to remove.

        Returns:
            self for chaining.
        """
        self._extra_resources.pop(resource_name, None)
        return self

    def required_resources(self) -> Set[str]:
        """Return required FrameGraph resources."""
        resources = set(self._extra_resources.keys())
        if self._required_depth:
            resources.add("depth")
        return resources

    def _get_material(self) -> "Material | None":
        """Get material from handle."""
        return self._material_handle.get_material_or_none() if self._material_handle else None

    def draw(
        self,
        gfx: "GraphicsBackend",
        context_key: int,
        color_tex: "GPUTextureHandle",
        extra_textures: dict[str, "GPUTextureHandle"],
        size: tuple[int, int],
        target_fbo=None,
    ):
        """Draw the post effect using the material's shader."""
        import numpy as np

        material = self._get_material()
        if material is None:
            # Fallback: just pass through color
            self._draw_passthrough(gfx, context_key, color_tex)
            return

        # Get first phase (post effects typically have one phase)
        if not material.phases:
            self._draw_passthrough(gfx, context_key, color_tex)
            return

        phase = material.phases[0]
        shader = phase.shader_programm

        if shader is None:
            self._draw_passthrough(gfx, context_key, color_tex)
            return

        shader.ensure_ready()
        shader.use()
        gfx.check_gl_error(f"MaterialPostEffect({self.name}): after shader.use")

        # Bind main color texture (use u_input_tex to avoid conflict with material's u_color)
        color_tex.bind(0)
        shader.set_uniform_int("u_input_tex", 0)
        gfx.check_gl_error(f"MaterialPostEffect({self.name}): after bind u_input_tex")

        # Bind extra resources as texture uniforms
        texture_unit = 1
        for resource_name, uniform_name in self._extra_resources.items():
            tex = extra_textures.get(resource_name)
            if tex is not None:
                tex.bind(texture_unit)
                shader.set_uniform_int(uniform_name, texture_unit)
                texture_unit += 1
        gfx.check_gl_error(f"MaterialPostEffect({self.name}): after extra resources")

        # Bind depth if required and available (legacy support)
        if self._required_depth and "depth" not in self._extra_resources:
            depth_tex = extra_textures.get("depth")
            if depth_tex is not None:
                depth_tex.bind(texture_unit)
                shader.set_uniform_int("u_depth", texture_unit)
                texture_unit += 1

        # Set resolution uniform
        w, h = size
        shader.set_uniform_vec2("u_resolution", float(w), float(h))
        gfx.check_gl_error(f"MaterialPostEffect({self.name}): after resolution")

        # Bind material textures (starting from next available unit)
        for tex_name, tex_handle in phase.textures.items():
            if tex_handle is not None:
                tex_handle.bind(texture_unit)
                shader.set_uniform_int(tex_name, texture_unit)
                texture_unit += 1
        gfx.check_gl_error(f"MaterialPostEffect({self.name}): after material textures")

        # Set material uniforms
        for uniform_name, uniform_value in phase.uniforms.items():
            self._set_uniform(shader, uniform_name, uniform_value)
            gfx.check_gl_error(f"MaterialPostEffect({self.name}): after uniform '{uniform_name}'")

        # Call before_draw callback for custom uniforms
        if self._before_draw is not None:
            self._before_draw(shader)
        gfx.check_gl_error(f"MaterialPostEffect({self.name}): after before_draw callback")

        # Draw fullscreen quad
        gfx.draw_ui_textured_quad(context_key)
        gfx.check_gl_error(f"MaterialPostEffect({self.name}): after draw_quad")

    def _set_uniform(self, shader, name: str, value) -> None:
        """Set uniform based on value type."""
        import numpy as np
        from termin.geombase import Vec3, Vec4

        if isinstance(value, (int, bool)):
            shader.set_uniform_int(name, int(value))
        elif isinstance(value, float):
            shader.set_uniform_float(name, value)
        elif isinstance(value, Vec3):
            shader.set_uniform_vec3(name, float(value.x), float(value.y), float(value.z))
        elif isinstance(value, Vec4):
            shader.set_uniform_vec4(name, float(value.x), float(value.y), float(value.z), float(value.w))
        elif isinstance(value, np.ndarray):
            if value.size == 2:
                shader.set_uniform_vec2(name, float(value[0]), float(value[1]))
            elif value.size == 3:
                shader.set_uniform_vec3(name, float(value[0]), float(value[1]), float(value[2]))
            elif value.size == 4:
                shader.set_uniform_vec4(name, float(value[0]), float(value[1]), float(value[2]), float(value[3]))
            elif value.size == 16:
                shader.set_uniform_mat4(name, value.astype(np.float32).flatten().tolist(), False)
        elif isinstance(value, (list, tuple)):
            arr = np.array(value, dtype=np.float32)
            self._set_uniform(shader, name, arr)

    def _draw_passthrough(
        self,
        gfx: "GraphicsBackend",
        context_key: int,
        color_tex: "GPUTextureHandle",
    ) -> None:
        """Fallback: pass through color unchanged."""
        from termin.visualization.render.framegraph.passes.present import PresentToScreenPass

        shader = PresentToScreenPass._get_shader()
        shader.ensure_ready()
        shader.use()
        shader.set_uniform_int("u_tex", 0)
        color_tex.bind(0)
        gfx.draw_ui_textured_quad(context_key)
