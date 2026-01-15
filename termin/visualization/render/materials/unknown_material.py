"""
Unknown/Missing Material - fallback for missing shaders and materials.

Used when:
- Shader file not found
- Material class not found
- Deserialization failed

Provides visual feedback (magenta color).
"""

from __future__ import annotations

from termin._native.render import TcMaterial, TcRenderState


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

def create_unknown_material(
    name: str = "UnknownMaterial",
    error_message: str | None = None,
) -> TcMaterial:
    """
    Create an unknown/missing material (bright magenta).

    Args:
        name: Material name (can include error info).
        error_message: Optional error message to store in name.

    Returns:
        TcMaterial that renders as magenta.
    """
    # Include error in name for debugging
    mat_name = name
    if error_message:
        mat_name = f"{name}: {error_message[:50]}"

    mat = TcMaterial.create(mat_name, "")
    mat.shader_name = "UnknownShader"

    state = TcRenderState.opaque()
    phase = mat.add_phase_from_sources(
        vertex_source=UNKNOWN_VERT,
        fragment_source=UNKNOWN_FRAG,
        geometry_source="",
        shader_name="UnknownShader",
        phase_mark="opaque",
        priority=0,
        state=state,
    )

    if phase is not None:
        # Magenta color
        phase.set_color(1.0, 0.0, 1.0, 1.0)

    return mat


# Legacy function alias
def get_unknown_shader():
    """Deprecated: Use create_unknown_material() instead."""
    raise NotImplementedError("get_unknown_shader() is deprecated. Use create_unknown_material() instead.")


class UnknownMaterial(TcMaterial):
    """
    Fallback material for missing/broken shaders and materials.

    Renders as bright magenta (standard "missing" color).
    Returns TcMaterial.
    """

    def __new__(
        cls,
        original_shader: str | None = None,
        original_material: str | None = None,
        original_data: dict | None = None,
        error_message: str | None = None,
    ) -> TcMaterial:
        # Build error message for debugging
        msg = error_message
        if not msg:
            if original_shader:
                msg = f"Missing shader: {original_shader}"
            elif original_material:
                msg = f"Missing material: {original_material}"
        return create_unknown_material(error_message=msg)

    @classmethod
    def for_missing_shader(cls, shader_name: str) -> TcMaterial:
        """Create UnknownMaterial for a missing shader."""
        return create_unknown_material(error_message=f"Missing shader: {shader_name}")

    @classmethod
    def for_missing_material(
        cls,
        material_name: str,
        original_data: dict | None = None,
    ) -> TcMaterial:
        """Create UnknownMaterial for a missing material class."""
        return create_unknown_material(error_message=f"Missing material: {material_name}")

    @classmethod
    def for_error(
        cls,
        error: Exception,
        original_data: dict | None = None,
    ) -> TcMaterial:
        """Create UnknownMaterial for a deserialization error."""
        return create_unknown_material(error_message=str(error))
