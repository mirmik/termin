"""Tests for shader skinning injection."""

import pytest

from termin.visualization.render.shader_skinning import (
    inject_skinning_into_vertex_shader,
    _find_last_layout_line,
    _find_main_function,
)


# Sample vertex shader (similar to DefaultMaterial)
SAMPLE_VERTEX_SHADER = """#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_uv;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_world_pos;
out vec3 v_normal;
out vec2 v_uv;

void main() {
    vec4 world = u_model * vec4(a_position, 1.0);
    v_world_pos = world.xyz;
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;
    v_uv = a_uv;
    gl_Position = u_projection * u_view * world;
}
"""


def test_find_last_layout_line():
    """Test finding the last layout declaration."""
    idx = _find_last_layout_line(SAMPLE_VERTEX_SHADER)
    lines = SAMPLE_VERTEX_SHADER.split('\n')
    assert idx >= 0
    assert 'layout' in lines[idx]
    assert 'a_uv' in lines[idx]  # Last layout is for a_uv


def test_find_main_function():
    """Test finding void main()."""
    main_decl, main_brace = _find_main_function(SAMPLE_VERTEX_SHADER)
    assert main_decl >= 0
    lines = SAMPLE_VERTEX_SHADER.split('\n')
    assert 'void main' in lines[main_decl]


def test_inject_skinning_basic():
    """Test basic skinning injection."""
    result = inject_skinning_into_vertex_shader(SAMPLE_VERTEX_SHADER)

    # Should have skinning uniforms
    assert 'u_bone_matrices' in result
    assert 'u_bone_count' in result

    # Should have skinning inputs
    assert 'a_joints' in result
    assert 'a_weights' in result

    # Should have skinning function
    assert '_applySkinning' in result

    # Should have replaced a_position and a_normal in main()
    assert '_skinned_position' in result
    assert '_skinned_normal' in result

    # Original declarations should still exist
    assert 'layout(location = 0) in vec3 a_position' in result
    assert 'layout(location = 1) in vec3 a_normal' in result


def test_inject_skinning_idempotent():
    """Test that injecting twice doesn't duplicate code."""
    result1 = inject_skinning_into_vertex_shader(SAMPLE_VERTEX_SHADER)
    result2 = inject_skinning_into_vertex_shader(result1)

    # Should be identical (skinning already present)
    assert result1 == result2


def test_inject_skinning_compiles():
    """Test that the resulting shader is valid GLSL (syntax check)."""
    result = inject_skinning_into_vertex_shader(SAMPLE_VERTEX_SHADER)

    # Basic syntax checks
    assert result.count('{') == result.count('}'), "Mismatched braces"

    # Check that main() still exists and is well-formed
    assert 'void main()' in result or 'void main ()' in result


def test_inject_skinning_preserves_structure():
    """Test that shader structure is preserved."""
    result = inject_skinning_into_vertex_shader(SAMPLE_VERTEX_SHADER)

    # #version should still be first non-empty line
    lines = [l for l in result.split('\n') if l.strip()]
    assert lines[0].startswith('#version')

    # Should still have all original outputs
    assert 'out vec3 v_world_pos' in result
    assert 'out vec3 v_normal' in result
    assert 'out vec2 v_uv' in result

    # Should still have original uniforms
    assert 'uniform mat4 u_model' in result
    assert 'uniform mat4 u_view' in result
    assert 'uniform mat4 u_projection' in result


def test_inject_skinning_replacement_only_in_main():
    """Test that a_position/a_normal are only replaced inside main()."""
    result = inject_skinning_into_vertex_shader(SAMPLE_VERTEX_SHADER)

    # The original layout declarations should be unchanged
    assert 'layout(location = 0) in vec3 a_position;' in result
    assert 'layout(location = 1) in vec3 a_normal;' in result

    # Inside main(), they should be replaced
    # Find the line with u_model * vec4(...)
    lines = result.split('\n')
    for line in lines:
        if 'u_model * vec4(' in line:
            assert '_skinned_position' in line
            break


# Shader with main() brace on same line
COMPACT_SHADER = """#version 330 core
layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
uniform mat4 u_mvp;
out vec3 v_normal;
void main() {
    gl_Position = u_mvp * vec4(a_position, 1.0);
    v_normal = a_normal;
}
"""


def test_inject_skinning_compact_main():
    """Test injection with compact main() style."""
    result = inject_skinning_into_vertex_shader(COMPACT_SHADER)

    assert 'u_bone_matrices' in result
    assert '_skinned_position' in result
    assert '_skinned_normal' in result


# Shader with main() brace on next line
EXPANDED_SHADER = """#version 330 core
layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
uniform mat4 u_mvp;
out vec3 v_normal;

void main()
{
    gl_Position = u_mvp * vec4(a_position, 1.0);
    v_normal = a_normal;
}
"""


def test_inject_skinning_expanded_main():
    """Test injection with expanded main() style (brace on next line)."""
    result = inject_skinning_into_vertex_shader(EXPANDED_SHADER)

    assert 'u_bone_matrices' in result
    assert '_skinned_position' in result
    assert '_skinned_normal' in result


# Shader without a_normal (position only)
POSITION_ONLY_SHADER = """#version 330 core
layout(location = 0) in vec3 a_position;
uniform mat4 u_mvp;

void main() {
    gl_Position = u_mvp * vec4(a_position, 1.0);
}
"""


def test_inject_skinning_position_only():
    """Test injection when shader only has a_position (no a_normal)."""
    result = inject_skinning_into_vertex_shader(POSITION_ONLY_SHADER)

    assert 'u_bone_matrices' in result
    assert '_skinned_position' in result
    # a_normal replacement should still be in the injected code
    assert '_skinned_normal' in result


# Shader with multiple functions
MULTI_FUNCTION_SHADER = """#version 330 core
layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
uniform mat4 u_model;
uniform mat4 u_vp;
out vec3 v_normal;

vec3 transformNormal(vec3 n) {
    return mat3(u_model) * n;
}

void main() {
    vec4 world = u_model * vec4(a_position, 1.0);
    v_normal = transformNormal(a_normal);
    gl_Position = u_vp * world;
}
"""


def test_inject_skinning_multi_function():
    """Test injection with helper functions before main()."""
    result = inject_skinning_into_vertex_shader(MULTI_FUNCTION_SHADER)

    assert 'u_bone_matrices' in result
    assert '_applySkinning' in result
    # Helper function should be preserved
    assert 'vec3 transformNormal' in result
    # Replacements should happen in main
    assert '_skinned_position' in result


# Shader with comments containing a_position
COMMENTED_SHADER = """#version 330 core
layout(location = 0) in vec3 a_position;  // vertex position
layout(location = 1) in vec3 a_normal;    // vertex normal
uniform mat4 u_mvp;
out vec3 v_normal;

void main() {
    // Transform a_position to clip space
    gl_Position = u_mvp * vec4(a_position, 1.0);
    v_normal = a_normal;  // pass through a_normal
}
"""


def test_inject_skinning_with_comments():
    """Test that comments containing a_position/a_normal are handled."""
    result = inject_skinning_into_vertex_shader(COMMENTED_SHADER)

    assert 'u_bone_matrices' in result
    # Comments in declarations should be preserved
    assert '// vertex position' in result
    # Variable usage should be replaced
    lines = result.split('\n')
    for line in lines:
        if 'u_mvp * vec4(' in line and '//' not in line.split('u_mvp')[0]:
            assert '_skinned_position' in line


# Shader with no layout declarations (old GLSL style)
NO_LAYOUT_SHADER = """#version 120
attribute vec3 a_position;
attribute vec3 a_normal;
uniform mat4 u_mvp;
varying vec3 v_normal;

void main() {
    gl_Position = u_mvp * vec4(a_position, 1.0);
    v_normal = a_normal;
}
"""


def test_inject_skinning_no_layout():
    """Test injection in shader without layout qualifiers."""
    result = inject_skinning_into_vertex_shader(NO_LAYOUT_SHADER)

    # Should still inject skinning
    assert 'u_bone_matrices' in result
    assert '_applySkinning' in result


# Shader with nested braces in main
NESTED_BRACES_SHADER = """#version 330 core
layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
uniform mat4 u_mvp;
uniform float u_time;
out vec3 v_normal;

void main() {
    vec3 pos = a_position;
    if (u_time > 0.0) {
        pos = pos * 1.1;
        if (u_time > 1.0) {
            pos = pos * 1.2;
        }
    }
    gl_Position = u_mvp * vec4(pos, 1.0);
    v_normal = a_normal;
}
"""


def test_inject_skinning_nested_braces():
    """Test injection with nested braces in main()."""
    result = inject_skinning_into_vertex_shader(NESTED_BRACES_SHADER)

    assert 'u_bone_matrices' in result
    # Braces should still be balanced
    assert result.count('{') == result.count('}')
    # Skinning should be applied
    assert '_skinned_position' in result


def test_inject_skinning_call_at_start_of_main():
    """Test that skinning call is at the very start of main() body."""
    result = inject_skinning_into_vertex_shader(SAMPLE_VERTEX_SHADER)

    lines = result.split('\n')
    main_found = False
    for i, line in enumerate(lines):
        if 'void main()' in line or 'void main ()' in line:
            main_found = True
            # Find opening brace
            brace_line = i if '{' in line else i + 1
            # Next non-empty line after brace should be skinning comment
            for j in range(brace_line + 1, len(lines)):
                stripped = lines[j].strip()
                if stripped:
                    assert 'Apply skinning' in stripped or '_skinned_position' in stripped, \
                        f"First statement after main() should be skinning, got: {stripped}"
                    break
            break

    assert main_found, "void main() not found"


# PBR-style shader (more complex)
PBR_STYLE_SHADER = """#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_uv;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;
uniform mat3 u_normal_matrix;

out vec3 v_world_pos;
out vec3 v_normal;
out vec2 v_uv;
out vec3 v_view_dir;

void main() {
    vec4 world_pos = u_model * vec4(a_position, 1.0);
    v_world_pos = world_pos.xyz;

    v_normal = normalize(u_normal_matrix * a_normal);
    v_uv = a_uv;

    vec4 view_pos = u_view * world_pos;
    v_view_dir = -view_pos.xyz;

    gl_Position = u_projection * view_pos;
}
"""


def test_inject_skinning_pbr_shader():
    """Test injection into PBR-style shader."""
    result = inject_skinning_into_vertex_shader(PBR_STYLE_SHADER)

    assert 'u_bone_matrices' in result
    assert '_skinned_position' in result
    assert '_skinned_normal' in result

    # Check that both usages of a_position are replaced
    lines = result.split('\n')
    for line in lines:
        # Skip declarations and skinning setup
        if 'layout' in line or '_applySkinning' in line or 'vec3 _skinned' in line:
            continue
        # In main body, a_position should be replaced
        if 'vec4(' in line and 'u_model' in line:
            assert 'a_position' not in line or '_skinned_position' in line


def test_inject_skinning_uniform_locations():
    """Test that injected uniforms use correct array syntax."""
    result = inject_skinning_into_vertex_shader(SAMPLE_VERTEX_SHADER)

    # Check uniform declarations
    assert 'uniform mat4 u_bone_matrices[MAX_BONES]' in result
    assert 'uniform int u_bone_count' in result
    assert 'const int MAX_BONES = 128' in result


def test_inject_skinning_input_locations():
    """Test that injected inputs use correct layout locations."""
    result = inject_skinning_into_vertex_shader(SAMPLE_VERTEX_SHADER)

    # a_joints should be at location 3, a_weights at location 4
    assert 'layout(location = 3) in vec4 a_joints' in result
    assert 'layout(location = 4) in vec4 a_weights' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
