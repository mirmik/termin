"""MaterialPostEffect - Post effect that uses a Material for rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING, Set

from termin.visualization.render.postprocess import PostEffect
from termin.visualization.core.material_handle import MaterialHandle
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, GPUTextureHandle
    from termin.visualization.core.material import Material


class MaterialPostEffect(PostEffect):
    """
    Post effect that uses a Material asset for rendering.

    This allows artists to create post effects using the material system,
    with custom shaders and parameters editable in the inspector.

    The material shader receives:
    - u_color: Main color texture (from previous pass)
    - u_depth: Depth texture (if required_depth=True)
    - u_resolution: vec2 with (width, height)

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

    def _serialize_params(self) -> dict:
        """Serialize parameters."""
        material_name = self._material_handle.get_name() if self._material_handle else ""
        return {
            "material_path": material_name or "",
            "required_depth": self._required_depth,
        }

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "MaterialPostEffect":
        """Create from serialized data."""
        instance = cls(
            material_path=data.get("material_path", ""),
            required_depth=data.get("required_depth", False),
        )
        if "name" in data:
            instance.name = data["name"]
        return instance

    def required_resources(self) -> Set[str]:
        """Return required FrameGraph resources."""
        resources = set()
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

        shader.ensure_ready(gfx)
        shader.use()

        # Bind main color texture
        color_tex.bind(0)
        shader.set_uniform_int("u_color", 0)

        # Bind depth if required and available
        texture_unit = 1
        if self._required_depth:
            depth_tex = extra_textures.get("depth")
            if depth_tex is not None:
                depth_tex.bind(texture_unit)
                shader.set_uniform_int("u_depth", texture_unit)
                texture_unit += 1

        # Set resolution uniform
        w, h = size
        shader.set_uniform_vec2("u_resolution", np.array([w, h], dtype=np.float32))

        # Bind material textures (starting from next available unit)
        for tex_name, tex_handle in phase.textures.items():
            if tex_handle is not None:
                tex_handle.bind(texture_unit)
                shader.set_uniform_int(tex_name, texture_unit)
                texture_unit += 1

        # Set material uniforms
        for uniform_name, uniform_value in phase.uniforms.items():
            self._set_uniform(shader, uniform_name, uniform_value)

        # Draw fullscreen quad
        gfx.draw_ui_textured_quad(context_key)

    def _set_uniform(self, shader, name: str, value) -> None:
        """Set uniform based on value type."""
        import numpy as np

        if isinstance(value, (int, bool)):
            shader.set_uniform_int(name, int(value))
        elif isinstance(value, float):
            shader.set_uniform_float(name, value)
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
        gfx: "GraphicsBackend",
        context_key: int,
        color_tex: "GPUTextureHandle",
    ) -> None:
        """Fallback: pass through color unchanged."""
        from termin.visualization.render.framegraph.passes.present import PresentToScreenPass

        shader = PresentToScreenPass._get_shader()
        shader.ensure_ready(gfx)
        shader.use()
        shader.set_uniform_int("u_tex", 0)
        color_tex.bind(0)
        gfx.draw_ui_textured_quad(context_key)
