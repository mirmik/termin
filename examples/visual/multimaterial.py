"""
demo_wire_cube.py

Куб с кастомным solid-шейдером.

Демонстрирует создание собственного ShaderProgram и Material.
"""

from __future__ import annotations

import numpy as np

from termin.geombase.pose3 import Pose3
from termin.mesh.mesh import CubeMesh
from termin.visualization import (
    Entity,
    MeshDrawable,
    Scene,
    Material,
    VisualizationWorld,
    PerspectiveCameraComponent,
    OrbitCameraController,
)
from termin.visualization.render.components import MeshRenderer, LightComponent
from termin.visualization.render.shader import ShaderProgram


# ----------------------------------------------------------------------
# SOLID SHADER (почти твой исходный)
# ----------------------------------------------------------------------

SOLID_VERT = """
#version 330 core

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

SOLID_FRAG = """
#version 330 core

in vec3 v_normal;
in vec3 v_world_pos;

uniform vec4 u_color;
uniform vec3 u_light_dir;
uniform vec3 u_light_color;
uniform vec3 u_view_pos;

out vec4 FragColor;

void main() {
    vec3 N = normalize(v_normal);
    vec3 L = normalize(-u_light_dir);
    vec3 V = normalize(u_view_pos - v_world_pos);
    vec3 H = normalize(L + V);

    const float ambientStrength  = 0.2;
    const float diffuseStrength  = 0.8;
    const float specularStrength = 0.4;
    const float shininess        = 32.0;

    vec3 ambient = ambientStrength * u_color.rgb;

    float ndotl = max(dot(N, L), 0.0);
    vec3 diffuse = diffuseStrength * ndotl * u_color.rgb;

    float specFactor = 0.0;
    if (ndotl > 0.0) {
        specFactor = pow(max(dot(N, H), 0.0), shininess);
    }
    vec3 specular = specularStrength * specFactor * u_light_color;

    vec3 color = (ambient + diffuse) * u_light_color + specular;
    color = clamp(color, 0.0, 1.0);

    FragColor = vec4(color, u_color.a);
}
"""


# ----------------------------------------------------------------------
# SCENE BUILDING
# ----------------------------------------------------------------------

def build_scene(world: VisualizationWorld):
    # Меш куба
    cube_mesh = CubeMesh()
    drawable = MeshDrawable(cube_mesh)

    # --- Solid материал ---
    solid_shader = ShaderProgram(SOLID_VERT, SOLID_FRAG)
    solid_material = Material(
        shader=solid_shader,
        color=np.array([0.8, 0.3, 0.3, 1.0], dtype=np.float32),
    )

    # --- Entity с MeshRenderer ---
    entity = Entity(pose=Pose3.identity(), name="cube")
    entity.add_component(
        MeshRenderer(
            mesh=drawable,
            material=solid_material,
        )
    )

    # --- Scene + камера ---
    scene = Scene()
    scene.add(entity)

    world.add_scene(scene)

    # Light
    light_entity = Entity(
        pose=Pose3.from_euler(np.deg2rad(-45), np.deg2rad(-45), 0),
        name="light",
    )
    light_entity.add_component(LightComponent())
    scene.add(light_entity)

    # Camera
    camera_entity = Entity(name="camera")
    camera = PerspectiveCameraComponent()
    camera_entity.add_component(camera)
    camera_entity.add_component(OrbitCameraController())
    scene.add(camera_entity)

    return scene, camera


def main():
    world = VisualizationWorld()
    scene, camera = build_scene(world)

    window = world.create_window(title="termin custom shader demo")
    window.add_viewport(scene, camera)

    world.run()


if __name__ == "__main__":
    main()
