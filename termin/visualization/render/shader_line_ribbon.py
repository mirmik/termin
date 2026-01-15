"""Shader line ribbon injection - converts lines to world-space ribbons via geometry shader."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from termin._native.render import TcMaterial, TcRenderState

if TYPE_CHECKING:
    from termin._native.render import TcShader


# Geometry shader that expands lines into billboard quads facing camera
# with round caps at segment ends for smooth joints
LINE_RIBBON_GEOMETRY_SHADER = """
#version 330 core

layout(lines) in;
// 4 for quad + 2 circles * 6 segments * 3 vertices = 4 + 36 = 40
layout(triangle_strip, max_vertices = 48) out;

in vec3 v_world_pos[];

uniform mat4 u_view;
uniform mat4 u_projection;
uniform float u_line_width;

const int CIRCLE_SEGMENTS = 6;
const float PI = 3.14159265359;

// Extract camera position from view matrix
vec3 get_camera_pos(mat4 view) {
    mat3 rot = mat3(view);
    vec3 d = vec3(view[3]);
    return -d * rot;
}

// Draw a circle at joint point (as separate triangles)
void emit_circle(vec3 center, vec3 perp, vec3 tangent, float radius, mat4 vp) {
    for (int i = 0; i < CIRCLE_SEGMENTS; i++) {
        float a0 = float(i) / float(CIRCLE_SEGMENTS) * 2.0 * PI;
        float a1 = float(i + 1) / float(CIRCLE_SEGMENTS) * 2.0 * PI;

        vec3 p0 = center + (perp * cos(a0) + tangent * sin(a0)) * radius;
        vec3 p1 = center + (perp * cos(a1) + tangent * sin(a1)) * radius;

        // Triangle: center -> p0 -> p1
        gl_Position = vp * vec4(center, 1.0);
        EmitVertex();
        gl_Position = vp * vec4(p0, 1.0);
        EmitVertex();
        gl_Position = vp * vec4(p1, 1.0);
        EmitVertex();
        EndPrimitive();
    }
}

void main() {
    vec3 p0 = v_world_pos[0];
    vec3 p1 = v_world_pos[1];

    vec3 camera_pos = get_camera_pos(u_view);

    // Line direction
    vec3 line_dir = normalize(p1 - p0);

    // Direction to camera (average for both ends)
    vec3 mid = (p0 + p1) * 0.5;
    vec3 to_camera = normalize(camera_pos - mid);

    // Perpendicular to line in plane facing camera (billboard)
    vec3 perp = normalize(cross(line_dir, to_camera));

    float half_width = u_line_width * 0.5;

    mat4 vp = u_projection * u_view;

    // Main quad
    vec3 v0 = p0 - perp * half_width;
    vec3 v1 = p0 + perp * half_width;
    vec3 v2 = p1 - perp * half_width;
    vec3 v3 = p1 + perp * half_width;

    gl_Position = vp * vec4(v0, 1.0);
    EmitVertex();
    gl_Position = vp * vec4(v1, 1.0);
    EmitVertex();
    gl_Position = vp * vec4(v2, 1.0);
    EmitVertex();
    gl_Position = vp * vec4(v3, 1.0);
    EmitVertex();
    EndPrimitive();

    // Round caps at both ends for smooth joints
    emit_circle(p0, perp, line_dir, half_width, vp);
    emit_circle(p1, perp, line_dir, half_width, vp);
}
"""


# Output declaration to add to vertex shader
LINE_RIBBON_VS_OUTPUT = """
// === Line ribbon output (injected) ===
out vec3 v_world_pos;
"""

# Code to add at beginning of vertex shader main()
LINE_RIBBON_VS_CALL = """    // === Compute world position for line ribbon (injected) ===
    v_world_pos = (u_model * vec4(a_position, 1.0)).xyz;
"""


def _inject_line_ribbon_into_vertex_shader(vertex_source: str) -> str:
    """
    Inject line ribbon output into vertex shader.

    Adds:
    - out vec3 v_world_pos declaration
    - v_world_pos computation in main()
    """
    # Check if already has line ribbon injection
    if 'v_world_pos' in vertex_source:
        return vertex_source

    lines = vertex_source.split('\n')

    # Find last layout line
    last_layout_line = -1
    for i, line in enumerate(lines):
        if re.match(r'\s*layout\s*\(', line):
            last_layout_line = i

    # Find main() opening brace
    main_brace_line = -1
    for i, line in enumerate(lines):
        if re.match(r'\s*void\s+main\s*\(\s*\)', line):
            if '{' in line:
                main_brace_line = i
            elif i + 1 < len(lines) and '{' in lines[i + 1]:
                main_brace_line = i + 1
            break

    if main_brace_line < 0:
        return vertex_source

    # Insert output declaration after last layout (or after #version)
    if last_layout_line >= 0:
        insert_decl_at = last_layout_line + 1
    else:
        insert_decl_at = 0
        for i, line in enumerate(lines):
            if line.strip().startswith('#version'):
                insert_decl_at = i + 1
                break

    # Build new source
    new_lines = []
    decl_lines = LINE_RIBBON_VS_OUTPUT.strip().split('\n')
    call_lines = LINE_RIBBON_VS_CALL.rstrip('\n').split('\n')

    for i, line in enumerate(lines):
        if i == insert_decl_at:
            new_lines.extend(decl_lines)
            new_lines.append('')

        new_lines.append(line)

        if i == main_brace_line:
            new_lines.extend(call_lines)

    return '\n'.join(new_lines)


def create_line_ribbon_shader_sources(
    vertex_source: str,
    fragment_source: str,
    geometry_source: str,
) -> tuple[str, str, str]:
    """
    Create shader sources with line ribbon geometry shader.

    Modifies vertex shader to output world position, and adds geometry
    shader that expands GL_LINES into world-space quads.

    Args:
        vertex_source: Original vertex shader source
        fragment_source: Original fragment shader source
        geometry_source: Original geometry shader source (may be empty)

    Returns:
        Tuple of (modified_vert, fragment, geometry) sources
    """
    # Don't inject if shader already has a geometry shader
    if geometry_source:
        return vertex_source, fragment_source, geometry_source

    # Modify vertex shader to output world position
    modified_vert = _inject_line_ribbon_into_vertex_shader(vertex_source)

    return modified_vert, fragment_source, LINE_RIBBON_GEOMETRY_SHADER


# Cache for line ribbon materials (keyed by material uuid)
_line_ribbon_material_cache: dict[str, TcMaterial] = {}


def get_line_ribbon_material(material: TcMaterial) -> TcMaterial:
    """
    Get or create a line ribbon variant of a TcMaterial.

    Args:
        material: Original TcMaterial

    Returns:
        TcMaterial with line ribbon geometry shader in all phases
    """
    mat_uuid = material.uuid
    if mat_uuid in _line_ribbon_material_cache:
        return _line_ribbon_material_cache[mat_uuid]

    # Create new material with line ribbon phases
    ribbon_mat = TcMaterial.create(
        name=f"{material.name}_LineRibbon" if material.name else "LineRibbon",
        uuid_hint=""
    )
    ribbon_mat.shader_name = material.shader_name
    ribbon_mat.source_path = material.source_path

    # Copy phases with modified shaders
    for i in range(material.phase_count):
        phase = material.get_phase(i)
        if phase is None:
            continue

        shader = material.get_phase_shader(i)
        if shader is None or not shader.is_valid:
            continue

        # Get original sources
        orig_vert = shader.vertex_source
        orig_frag = shader.fragment_source
        orig_geom = shader.geometry_source

        # Create ribbon variant sources
        vert, frag, geom = create_line_ribbon_shader_sources(orig_vert, orig_frag, orig_geom)

        # Create new phase with ribbon shader
        state = material.get_phase_render_state(i)
        new_phase = ribbon_mat.add_phase_from_sources(
            vertex_source=vert,
            fragment_source=frag,
            geometry_source=geom,
            shader_name=f"{material.shader_name}_LineRibbon",
            phase_mark=phase.phase_mark,
            priority=phase.priority,
            state=state,
        )

        if new_phase is not None:
            # Copy uniforms from original phase
            # Phase uniforms are applied via TcMaterial methods
            pass  # Uniforms will be applied by LineRenderer before draw

    _line_ribbon_material_cache[mat_uuid] = ribbon_mat
    return ribbon_mat


def clear_line_ribbon_cache() -> None:
    """Clear all cached line ribbon variants."""
    _line_ribbon_material_cache.clear()
