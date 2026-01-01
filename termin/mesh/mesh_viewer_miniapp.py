"""Minimal demo that renders a cube and allows orbiting camera controls."""

from __future__ import annotations

import numpy as np

from termin.geombase import Pose3
from termin.visualization import (
    Entity,
    Scene,
    Material,
    VisualizationWorld,
    PerspectiveCameraComponent,
    OrbitCameraController,
)
from termin.voxels.voxel_mesh import create_voxel_mesh
from termin.visualization.render.components import MeshRenderer, LineRenderer
from termin.visualization.render.shader import ShaderProgram

vert = """
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_normal;     // нормаль в мировом пространстве
out vec3 v_world_pos;  // позиция в мировом пространстве

void main() {
    vec4 world = u_model * vec4(a_position, 1.0);
    v_world_pos = world.xyz;

    // нормальная матрица = mat3(transpose(inverse(u_model)))
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;

    gl_Position = u_projection * u_view * world;
}
"""


frag = """
#version 330 core

in vec3 v_normal;
in vec3 v_world_pos;

uniform vec4 u_color;        // базовый цвет материала (RGBA)
uniform vec3 u_light_dir;    // направление от источника к объекту (world space)
uniform vec3 u_light_color;  // цвет света
uniform vec3 u_view_pos;     // позиция камеры (world space)

out vec4 FragColor;

void main() {
    // Нормаль
    vec3 N = normalize(v_normal);

    // Направление на свет: если u_light_dir - направление *от* света, то на объект оно то же
    vec3 L = normalize(-u_light_dir); // если задаёшь уже "к объекту", убери минус

    // Направление на камеру
    vec3 V = normalize(u_view_pos - v_world_pos);

    // Полуунитектор (half-vector) для Blinn–Phong
    vec3 H = normalize(L + V);

    // --- коэффициенты освещения ---
    const float ambientStrength  = 0.2;  // эмбиент
    const float diffuseStrength  = 0.8;  // диффуз
    const float specularStrength = 0.4;  // спекуляр
    const float shininess        = 32.0; // степень блеска

    // Эмбиент
    vec3 ambient = ambientStrength * u_color.rgb;

    // Диффуз (Ламберт)
    float ndotl = max(dot(N, L), 0.0);
    vec3 diffuse = diffuseStrength * ndotl * u_color.rgb;

    // Спекуляр (Blinn–Phong)
    float specFactor = 0.0;
    if (ndotl > 0.0) {
        specFactor = pow(max(dot(N, H), 0.0), shininess);
    }
    vec3 specular = specularStrength * specFactor * u_light_color;

    // Итоговый цвет: модифицируем цвет материала цветом света
    vec3 color = (ambient + diffuse) * u_light_color + specular;

    // Можно слегка ограничить, чтобы не улетало в дикий перегиб
    color = clamp(color, 0.0, 1.0);

    FragColor = vec4(color, u_color.a);
}
"""

def build_scene(world: VisualizationWorld, mesh: "Mesh") -> tuple[Scene, PerspectiveCameraComponent]:

    scene = Scene()

    mesh_tc = create_voxel_mesh(
        vertices=mesh.vertices,
        triangles=mesh.triangles,
        vertex_normals=mesh.vertex_normals if hasattr(mesh, 'vertex_normals') else None,
        name="mesh",
    )
    shader_prog = ShaderProgram(vert, frag)
    material = Material(shader=shader_prog, color=np.array([0.8, 0.3, 0.3, 1.0], dtype=np.float32))
    entity = Entity(pose=Pose3.identity(), name="cube")
    entity.add_component(MeshRenderer(mesh_tc, material))
    
    scene.add(entity)

    world.add_scene(scene)

    T = 10000.0
    coord_lines = Entity(name="coord_lines")
    coord_lines.add_component(LineRenderer(points=[(0,0,-T), (0,0,T)], color=(1,0,0,1), width=2.0))  # Z - красная
    coord_lines.add_component(LineRenderer(points=[(0,-T,0), (0,T,0)], color=(0,1,0,1), width=2.0))  # Y - зелёная
    coord_lines.add_component(LineRenderer(points=[(-T,0,0), (T,0,0)], color=(0,0,1,1), width=2.0))  # X - синяя
    scene.add(coord_lines)

    camera_entity = Entity(name="camera")
    camera = PerspectiveCameraComponent()
    camera_entity.add_component(camera)
    camera_entity.add_component(OrbitCameraController())
    scene.add(camera_entity)

    return scene, camera


def show_mesh_app(mesh: "Mesh"):
    world = VisualizationWorld()
    scene, camera = build_scene(world, mesh)
    window = world.create_window(title="termin cube demo")
    window.add_viewport(scene, camera)
    world.run()


if __name__ == "__main__":
    main()
