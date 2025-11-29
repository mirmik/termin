"""Textured cube demo using the component-based visualization world."""

from __future__ import annotations

import numpy as np

from termin.geombase.pose3 import Pose3
from termin.mesh.mesh import TexturedCubeMesh
from termin.visualization import (
    Entity,
    MeshDrawable,
    Scene,
    Material,
    Texture,
    VisualizationWorld,
    PerspectiveCameraComponent,
    OrbitCameraController,
)
from termin.visualization.render.components import MeshRenderer
from termin.visualization.render.shader import ShaderProgram
from termin.visualization.render.skybox import SkyBoxEntity


VERT = """
#version 330 core
layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_texcoord;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_normal;
out vec3 v_world_pos;
out vec2 v_texcoord;

void main() {
    vec4 world = u_model * vec4(a_position, 1.0);
    v_world_pos = world.xyz;
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;
    v_texcoord = a_texcoord;
    gl_Position = u_projection * u_view * world;
}
"""


FRAG = """
#version 330 core
in vec3 v_normal;
in vec3 v_world_pos;
in vec2 v_texcoord;

uniform vec3 u_light_dir;
uniform vec3 u_light_color;
uniform vec3 u_view_pos;
uniform sampler2D u_diffuse_map;

out vec4 FragColor;

void main() {
    vec3 N = normalize(v_normal);
    vec3 L = normalize(-u_light_dir);
    vec3 V = normalize(u_view_pos - v_world_pos);
    vec3 texColor = texture(u_diffuse_map, v_texcoord).rgb;
    float ndotl = max(dot(N, L), 0.0);
    vec3 diffuse = texColor * ndotl;
    vec3 ambient = texColor * 0.2;
    vec3 H = normalize(L + V);
    float spec = pow(max(dot(N, H), 0.0), 32.0);
    vec3 specular = vec3(0.4) * spec;
    vec3 color = (ambient + diffuse) * u_light_color + specular;
    FragColor = vec4(color, 1.0);
}
"""


def build_scene(world: VisualizationWorld) -> tuple[Scene, PerspectiveCameraComponent]:
    texture_path = "examples/data/textures/crate_diffuse.png"
    texture = Texture.from_file(texture_path)
    mesh = TexturedCubeMesh()
    drawable = MeshDrawable(mesh)
    shader_prog = ShaderProgram(VERT, FRAG)
    material = Material(shader=shader_prog, color=None, textures={"u_diffuse_map": texture})

    cube = Entity(pose=Pose3.identity(), name="cube")
    cube.add_component(MeshRenderer(drawable, material))

    scene = Scene()
    scene.add(cube)
    scene.add(SkyBoxEntity())
    world.add_scene(scene)

    camera1_entity = Entity(name="camera1")
    camera1 = PerspectiveCameraComponent()
    camera1_entity.add_component(camera1)
    camera1_entity.add_component(OrbitCameraController())
    scene.add(camera1_entity)

    camera2_entity = Entity(name="camera2")
    camera2 = PerspectiveCameraComponent()
    camera2_entity.add_component(camera2)
    camera2_entity.add_component(OrbitCameraController())
    scene.add(camera2_entity)

    return scene, camera1, camera2


def main():
    world = VisualizationWorld()
    scene, camera1, camera2 = build_scene(world)
    window1 = world.create_window(title="window1")
    window2 = world.create_window(title="window2")
    window1.add_viewport(scene, camera1)
    window2.add_viewport(scene, camera2)
    world.run()


if __name__ == "__main__":
    main()
