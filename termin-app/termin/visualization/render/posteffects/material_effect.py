"""MaterialPostEffect - Post effect that uses a Material for rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional, Set

from termin.visualization.render.postprocess import PostEffect
from termin._native.render import TcMaterial
from termin.editor.inspect_field import InspectField
from tcbase import log

if TYPE_CHECKING:
    from tgfx import TcShader

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
            path="_material",
            label="Material",
            kind="tc_material",
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
        self._material = TcMaterial()
        if material_path:
            self._material = TcMaterial.from_name(material_path)
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

    def _get_material(self) -> "TcMaterial | None":
        """Get material."""
        return self._material if self._material.is_valid else None

    def draw(self, ctx2, color_tex2, target_tex2, extra_tex2, size):
        """Draw the post effect using the material's shader."""
        from tgfx._tgfx_native import tc_shader_ensure_tgfx2

        material = self._get_material()
        if material is None or not material.phases:
            self._draw_passthrough(ctx2, color_tex2, target_tex2, size)
            return

        phase = material.phases[0]
        shader = phase.shader
        if not shader.is_valid:
            self._draw_passthrough(ctx2, color_tex2, target_tex2, size)
            return

        pair = tc_shader_ensure_tgfx2(ctx2, shader)
        if not pair.vs or not pair.fs:
            self._draw_passthrough(ctx2, color_tex2, target_tex2, size)
            return

        def setup(ctx2):
            ctx2.bind_shader(pair.vs, pair.fs)

            ctx2.bind_sampled_texture(0, color_tex2)
            ctx2.set_uniform_int("u_input_tex", 0)

            texture_unit = 1
            for resource_name, uniform_name in self._extra_resources.items():
                tex2 = extra_tex2.get(resource_name)
                if tex2 is not None:
                    ctx2.bind_sampled_texture(texture_unit, tex2)
                    ctx2.set_uniform_int(uniform_name, texture_unit)
                    texture_unit += 1

            if self._required_depth and "depth" not in self._extra_resources:
                depth_tex2 = extra_tex2.get("depth")
                if depth_tex2 is not None:
                    ctx2.bind_sampled_texture(texture_unit, depth_tex2)
                    ctx2.set_uniform_int("u_depth", texture_unit)

            w, h = size
            ctx2.set_uniform_vec2("u_resolution", float(w), float(h))

            for uniform_name, uniform_value in phase.uniforms.items():
                self._set_uniform(ctx2, uniform_name, uniform_value)

            if self._before_draw is not None:
                self._before_draw(shader)

            ctx2.draw_fullscreen_quad()

        PostEffect._simple_draw(ctx2, target_tex2, size, setup)

    def _set_uniform(self, ctx2, name: str, value) -> None:
        """Set uniform on the tgfx2 context based on value type."""
        import numpy as np
        from termin.geombase import Vec3, Vec4

        if isinstance(value, (int, bool)):
            ctx2.set_uniform_int(name, int(value))
        elif isinstance(value, float):
            ctx2.set_uniform_float(name, value)
        elif isinstance(value, Vec3):
            ctx2.set_uniform_vec3(name, float(value.x), float(value.y), float(value.z))
        elif isinstance(value, Vec4):
            ctx2.set_uniform_vec4(name, float(value.x), float(value.y), float(value.z), float(value.w))
        elif isinstance(value, np.ndarray):
            if value.size == 2:
                ctx2.set_uniform_vec2(name, float(value[0]), float(value[1]))
            elif value.size == 3:
                ctx2.set_uniform_vec3(name, float(value[0]), float(value[1]), float(value[2]))
            elif value.size == 4:
                ctx2.set_uniform_vec4(name, float(value[0]), float(value[1]), float(value[2]), float(value[3]))
        elif isinstance(value, (list, tuple)):
            arr = np.array(value, dtype=np.float32)
            self._set_uniform(ctx2, name, arr)

    def _draw_passthrough(self, ctx2, color_tex2, target_tex2, size) -> None:
        """Fallback: pass through color unchanged via a minimal blit shader."""
        from tgfx._tgfx_native import tc_shader_ensure_tgfx2
        from termin.visualization.render.framegraph.passes.present import PresentToScreenPass

        shader = PresentToScreenPass._get_shader()
        pair = tc_shader_ensure_tgfx2(ctx2, shader)
        if not pair.vs or not pair.fs:
            return

        def setup(ctx2):
            ctx2.bind_shader(pair.vs, pair.fs)
            ctx2.bind_sampled_texture(0, color_tex2)
            ctx2.set_uniform_int("u_tex", 0)
            ctx2.draw_fullscreen_quad()

        PostEffect._simple_draw(ctx2, target_tex2, size, setup)
