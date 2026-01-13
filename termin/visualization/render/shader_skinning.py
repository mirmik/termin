"""Shader skinning injection - automatically adds skeletal animation support to any shader."""

from __future__ import annotations

import re
import weakref

from termin.visualization.core.material import Material, MaterialPhase
from termin.visualization.render.shader import ShaderProgram


# Skinning inputs to inject after existing layout declarations
SKINNING_INPUTS = """
// === Skinning inputs (injected) ===
layout(location = 3) in vec4 a_joints;
layout(location = 4) in vec4 a_weights;

const int MAX_BONES = 128;
uniform mat4 u_bone_matrices[MAX_BONES];
uniform int u_bone_count;
"""

# Skinning function to inject before main() - full version with normals
SKINNING_FUNCTION = """
// === Skinning function (injected) ===
void _applySkinning(inout vec3 position, inout vec3 normal) {
    if (u_bone_count <= 0) return;

    vec4 skinned_pos = vec4(0.0);
    vec3 skinned_norm = vec3(0.0);

    for (int i = 0; i < 4; ++i) {
        int idx = int(a_joints[i]);
        float w = a_weights[i];
        if (w > 0.0 && idx < u_bone_count) {
            mat4 bone = u_bone_matrices[idx];
            skinned_pos += w * (bone * vec4(position, 1.0));
            skinned_norm += w * (mat3(bone) * normal);
        }
    }

    position = skinned_pos.xyz;
    normal = skinned_norm;
}
"""

# Skinning function - position only (for shaders without normals)
SKINNING_FUNCTION_POS_ONLY = """
// === Skinning function (injected, position only) ===
void _applySkinning(inout vec3 position) {
    if (u_bone_count <= 0) return;

    vec4 skinned_pos = vec4(0.0);

    for (int i = 0; i < 4; ++i) {
        int idx = int(a_joints[i]);
        float w = a_weights[i];
        if (w > 0.0 && idx < u_bone_count) {
            mat4 bone = u_bone_matrices[idx];
            skinned_pos += w * (bone * vec4(position, 1.0));
        }
    }

    position = skinned_pos.xyz;
}
"""

# Call to add at the beginning of main() - full version
SKINNING_CALL = """    // === Apply skinning (injected) ===
    vec3 _skinned_position = a_position;
    vec3 _skinned_normal = a_normal;
    _applySkinning(_skinned_position, _skinned_normal);
"""

# Call - position only version
SKINNING_CALL_POS_ONLY = """    // === Apply skinning (injected, position only) ===
    vec3 _skinned_position = a_position;
    _applySkinning(_skinned_position);
"""


def _find_last_layout_line(source: str) -> int:
    """Find the line number after the last layout(...) in declaration."""
    lines = source.split('\n')
    last_layout_line = -1

    for i, line in enumerate(lines):
        # Match layout declarations (not in functions)
        if re.match(r'\s*layout\s*\(', line):
            last_layout_line = i

    return last_layout_line


def _find_main_function(source: str) -> Tuple[int, int]:
    """
    Find void main() function.

    Returns:
        (line_of_void_main, line_of_opening_brace)
    """
    lines = source.split('\n')

    for i, line in enumerate(lines):
        if re.match(r'\s*void\s+main\s*\(\s*\)', line):
            # Check if { is on the same line or next line
            if '{' in line:
                return i, i
            elif i + 1 < len(lines) and '{' in lines[i + 1]:
                return i, i + 1

    return -1, -1


def inject_skinning_into_vertex_shader(vertex_source: str) -> str:
    """
    Inject skinning code into a vertex shader.

    Transforms:
    - Adds a_joints, a_weights inputs
    - Adds u_bone_matrices, u_bone_count uniforms
    - Adds _applySkinning() function
    - Replaces a_position (and a_normal if present) with skinned versions

    Args:
        vertex_source: Original vertex shader source

    Returns:
        Modified vertex shader with skinning support
    """
    # Check if already has skinning
    if 'u_bone_matrices' in vertex_source:
        return vertex_source

    lines = source_lines = vertex_source.split('\n')

    # Check if shader has a_normal (some shaders like shadow/pick don't need normals)
    has_normal = bool(re.search(r'\ba_normal\b', vertex_source))

    # 1. Find insertion points
    last_layout = _find_last_layout_line(vertex_source)
    main_decl, main_brace = _find_main_function(vertex_source)

    if main_decl < 0:
        raise ValueError("Could not find void main() in vertex shader")

    # 2. Insert skinning inputs after last layout (or after #version if no layouts)
    if last_layout >= 0:
        insert_inputs_at = last_layout + 1
    else:
        # Find #version line
        for i, line in enumerate(lines):
            if line.strip().startswith('#version'):
                insert_inputs_at = i + 1
                break
        else:
            insert_inputs_at = 0

    # 3. Insert skinning function before main()
    insert_func_at = main_decl

    # 4. Insert skinning call after opening brace of main()
    insert_call_at = main_brace + 1

    # Build new source (work backwards to preserve line numbers)
    result_lines = list(lines)

    # Choose version based on whether shader uses normals
    if has_normal:
        skinning_call_lines = SKINNING_CALL.rstrip('\n').split('\n')
        skinning_func_lines = SKINNING_FUNCTION.strip().split('\n')
    else:
        skinning_call_lines = SKINNING_CALL_POS_ONLY.rstrip('\n').split('\n')
        skinning_func_lines = SKINNING_FUNCTION_POS_ONLY.strip().split('\n')

    # Insert inputs after layouts
    skinning_input_lines = SKINNING_INPUTS.strip().split('\n')

    # Calculate offsets
    # We need to insert in reverse order to keep indices valid

    # First, build the new source by sections
    new_lines = []

    for i, line in enumerate(lines):
        # Add inputs after last layout
        if i == insert_inputs_at:
            new_lines.extend(skinning_input_lines)
            new_lines.append('')

        # Add function before main
        if i == insert_func_at:
            new_lines.append('')
            new_lines.extend(skinning_func_lines)
            new_lines.append('')

        new_lines.append(line)

        # Add call after opening brace
        if i == main_brace:
            new_lines.extend(skinning_call_lines)

    result = '\n'.join(new_lines)

    # 5. Replace a_position and a_normal with skinned versions in main() body
    # We need to be careful to only replace within main(), not in declarations

    # Find main() body boundaries in the new source
    new_main_decl, new_main_brace = _find_main_function(result)
    if new_main_brace < 0:
        return result

    new_lines = result.split('\n')

    # Find closing brace of main (simple brace counting)
    brace_count = 0
    main_start = new_main_brace
    main_end = len(new_lines)

    for i in range(new_main_brace, len(new_lines)):
        line = new_lines[i]
        brace_count += line.count('{') - line.count('}')
        if brace_count == 0 and i > new_main_brace:
            main_end = i
            break

    # Replace a_position and a_normal only within main() body
    # Skip the skinning call lines we just inserted
    skinning_call_end = main_start + len(skinning_call_lines) + 1

    for i in range(skinning_call_end, main_end + 1):
        if i < len(new_lines):
            # Replace a_position with _skinned_position
            new_lines[i] = re.sub(r'\ba_position\b', '_skinned_position', new_lines[i])
            # Replace a_normal with _skinned_normal
            new_lines[i] = re.sub(r'\ba_normal\b', '_skinned_normal', new_lines[i])

    result = '\n'.join(new_lines)
    return result


def get_skinned_shader(shader: ShaderProgram) -> ShaderProgram:
    """
    Get or create a skinned variant of a shader.

    Uses source-hash based registry for caching.

    Args:
        shader: Original shader program

    Returns:
        Shader with skinning support injected
    """
    # Check if already has skinning (avoid double-injection)
    if 'u_bone_matrices' in shader.vertex_source:
        return shader

    from termin.visualization.render.shader_variants import (
        get_variant_registry,
        ShaderVariantOp,
    )

    registry = get_variant_registry()
    return registry.get_variant(shader, ShaderVariantOp.SKINNING)


# Cache for skinned material variants keyed by material id
# Cleared via clear_skinning_cache() when shaders are reloaded
# Note: Cannot use WeakKeyDictionary because C++ Material objects don't support weak references
_skinned_material_cache: dict[int, Material] = {}


def get_skinned_material(material: Material) -> Material:
    """
    Get or create a skinned variant of a material.

    Creates a new material with all phases having skinning-enabled shaders.

    Args:
        material: Original material

    Returns:
        Material with skinning support
    """
    mat_id = id(material)
    if mat_id in _skinned_material_cache:
        return _skinned_material_cache[mat_id]

    # Create new material with skinned phases
    skinned_mat = Material()
    skinned_mat.name = f"{material.name}_Skinned" if material.name else "Skinned"
    skinned_mat.source_path = material.source_path
    skinned_mat.shader_name = material.shader_name

    # Build phases list first (nanobind doesn't support append on vector members)
    new_phases = []
    for phase in material.phases:
        skinned_shader = get_skinned_shader(phase.shader_programm)
        skinned_phase = MaterialPhase(
            shader_programm=skinned_shader,
            render_state=phase.render_state,
            phase_mark=phase.phase_mark,
            priority=phase.priority,
            textures=dict(phase.textures),
            uniforms=dict(phase.uniforms),  # includes u_color
        )
        new_phases.append(skinned_phase)

    # Assign all phases at once
    skinned_mat.phases = new_phases
    _skinned_material_cache[mat_id] = skinned_mat
    return skinned_mat


def clear_skinning_cache() -> None:
    """Clear all cached skinned variants. Call when shaders are reloaded."""
    from termin.visualization.render.shader_variants import (
        get_variant_registry,
        ShaderVariantOp,
    )

    # Clear shader variants from registry
    registry = get_variant_registry()
    registry.clear_operation(ShaderVariantOp.SKINNING)

    # Clear material cache
    _skinned_material_cache.clear()
