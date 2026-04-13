# skybox.py
"""Skybox shaders and geometry utilities."""

from __future__ import annotations
import numpy as np


SKYBOX_VERTEX_SHADER = """
#version 330 core
layout(location = 0) in vec3 a_position;

uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_dir;

void main() {
    // Убираем трансляцию камеры — skybox не должен двигаться
    mat4 view_no_translation = mat4(mat3(u_view));
    v_dir = a_position;
    gl_Position = u_projection * view_no_translation * vec4(a_position, 1.0);
}
"""

SKYBOX_GRADIENT_FRAGMENT_SHADER = """
#version 330 core

in vec3 v_dir;
out vec4 FragColor;

uniform vec3 u_skybox_top_color;
uniform vec3 u_skybox_bottom_color;

void main() {
    // Вертикальный градиент по оси Z (вверх в нашей СК)
    float t = normalize(v_dir).z * 0.5 + 0.5;
    FragColor = vec4(mix(u_skybox_bottom_color, u_skybox_top_color, t), 1.0);
}
"""

# Keep old name for compatibility
SKYBOX_FRAGMENT_SHADER = SKYBOX_GRADIENT_FRAGMENT_SHADER

SKYBOX_SOLID_FRAGMENT_SHADER = """
#version 330 core

in vec3 v_dir;
out vec4 FragColor;

uniform vec3 u_skybox_color;

void main() {
    FragColor = vec4(u_skybox_color, 1.0);
}
"""


def _skybox_cube():
    F = 1.0  # большой размер куба
    vertices = np.array([
        [-F, -F, -F],
        [ F, -F, -F],
        [ F,  F, -F],
        [-F,  F, -F],
        [-F, -F,  F],
        [ F, -F,  F],
        [ F,  F,  F],
        [-F,  F,  F],
    ], dtype=np.float32)

    triangles = np.array([
        [0, 1, 2], [0, 2, 3],      # back
        [4, 6, 5], [4, 7, 6],      # front
        [0, 4, 5], [0, 5, 1],      # bottom
        [3, 2, 6], [3, 6, 7],      # top
        [1, 5, 6], [1, 6, 2],      # right
        [0, 3, 7], [0, 7, 4],      # left
    ], dtype=np.uint32)

    return vertices, triangles
