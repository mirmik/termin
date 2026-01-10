"""
Unknown/Missing Material - fallback for missing shaders and materials.

Used when:
- Shader file not found
- Material class not found
- Deserialization failed

Provides visual feedback (magenta color) and preserves original reference
for later recovery.
"""

from __future__ import annotations

from typing import Any

from termin.visualization.core.material import Material
from termin.visualization.render.shader import ShaderProgram


UNKNOWN_VERT = """#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_normal;
out vec3 v_world_pos;

void main() {
    vec4 world = u_model * vec4(a_position, 1.0);
    v_world_pos = world.xyz;
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;
    gl_Position = u_projection * u_view * world;
}
"""

UNKNOWN_FRAG = """#version 330 core

in vec3 v_normal;
in vec3 v_world_pos;

uniform vec3 u_camera_position;

out vec4 FragColor;

void main() {
    vec3 N = normalize(v_normal);
    vec3 V = normalize(u_camera_position - v_world_pos);

    // Simple hemisphere lighting
    float up = dot(N, vec3(0.0, 0.0, 1.0)) * 0.5 + 0.5;

    // Magenta base color (standard "missing texture" color)
    vec3 base_color = vec3(1.0, 0.0, 1.0);

    // Fresnel rim for visibility
    float fresnel = pow(1.0 - max(dot(N, V), 0.0), 3.0);

    vec3 color = base_color * (0.3 + 0.7 * up) + vec3(1.0) * fresnel * 0.3;

    FragColor = vec4(color, 1.0);
}
"""

_unknown_shader: ShaderProgram | None = None


def get_unknown_shader() -> ShaderProgram:
    """Get or create the unknown/missing shader."""
    global _unknown_shader
    if _unknown_shader is None:
        _unknown_shader = ShaderProgram(
            vertex_source=UNKNOWN_VERT,
            fragment_source=UNKNOWN_FRAG
        )
    return _unknown_shader


class UnknownMaterial(Material):
    """
    Fallback material for missing/broken shaders and materials.

    Renders as bright magenta (standard "missing" color) with simple
    hemisphere lighting. Stores the original reference for debugging
    and potential recovery.

    Attributes:
        original_shader: Name of the shader that was not found
        original_material: Name of the material class that was not found
        original_data: Serialized data that failed to deserialize
        error_message: Description of what went wrong
    """

    original_shader: str | None = None
    original_material: str | None = None
    original_data: dict | None = None
    error_message: str | None = None

    def __init__(
        self,
        original_shader: str | None = None,
        original_material: str | None = None,
        original_data: dict | None = None,
        error_message: str | None = None,
    ):
        shader = get_unknown_shader()
        super().__init__(shader=shader, color=(1.0, 0.0, 1.0, 1.0))

        self.original_shader = original_shader
        self.original_material = original_material
        self.original_data = original_data
        self.error_message = error_message

    def serialize(self) -> dict:
        """
        Serialize preserving original data for recovery.

        If original_data exists, return it unchanged so the scene
        can be saved and loaded again when the missing resource
        becomes available.
        """
        if self.original_data is not None:
            return self.original_data

        return {
            "type": "UnknownMaterial",
            "original_shader": self.original_shader,
            "original_material": self.original_material,
            "error_message": self.error_message,
        }

    @classmethod
    def for_missing_shader(cls, shader_name: str) -> "UnknownMaterial":
        """Create UnknownMaterial for a missing shader."""
        return cls(
            original_shader=shader_name,
            error_message=f"Shader not found: {shader_name}",
        )

    @classmethod
    def for_missing_material(
        cls,
        material_name: str,
        original_data: dict | None = None,
    ) -> "UnknownMaterial":
        """Create UnknownMaterial for a missing material class."""
        return cls(
            original_material=material_name,
            original_data=original_data,
            error_message=f"Material class not found: {material_name}",
        )

    @classmethod
    def for_error(
        cls,
        error: Exception,
        original_data: dict | None = None,
    ) -> "UnknownMaterial":
        """Create UnknownMaterial for a deserialization error."""
        return cls(
            original_data=original_data,
            error_message=str(error),
        )

    def __repr__(self) -> str:
        if self.original_shader:
            return f"<UnknownMaterial shader={self.original_shader!r}>"
        if self.original_material:
            return f"<UnknownMaterial material={self.original_material!r}>"
        return f"<UnknownMaterial error={self.error_message!r}>"
