"""
Textured cube demo + grayscale + Gaussian blur (two-pass)
Всё в одном файле, как ты просил.
"""

from __future__ import annotations
import numpy as np

from termin.geombase import Pose3
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
from tgfx import TcShader
from termin.visualization.render.posteffects.gray import GrayscaleEffect
from termin.visualization.render.posteffects.blur import GaussianBlurPass

# ================================================================
#          СЦЕНА
# ================================================================

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


def build_scene(world):
    texture_path = "examples/data/textures/crate_diffuse.png"
    texture = Texture.from_file(texture_path)

    mesh = TexturedCubeMesh()
    drawable = MeshDrawable(mesh)
    material = Material(
        shader=TcShader.from_sources(VERT, FRAG, "", "TextCubeShader"),
        color=None,
        textures={"u_diffuse_map": texture},
    )

    cube = Entity(pose=Pose3.identity())
    cube.add_component(MeshRenderer(drawable, material))

    scene = Scene()
    scene.add(cube)
    world.add_scene(scene)

    cam_ent = Entity()
    cam = PerspectiveCameraComponent()
    cam_ent.add_component(cam)
    cam_ent.add_component(OrbitCameraController())
    scene.add(cam_ent)

    return scene, cam


# ================================================================
#          MAIN
# ================================================================

def main():
    world = VisualizationWorld()

    scene, cam = build_scene(world)

    win = world.create_window(title="Cube + Grayscale + Gaussian Blur")
    vp = win.add_viewport(scene, cam)

    # Используем новый API через world.find_render_pass()
    postprocess = world.find_render_pass(vp, "PostFX")

    # цепочка: Grayscale → Blur Horizontal → Blur Vertical
    postprocess.add_effect(GrayscaleEffect())
    postprocess.add_effect(GaussianBlurPass(direction=(1.0, 0.0)))  # horizontal
    postprocess.add_effect(GaussianBlurPass(direction=(0.0, 1.0)))  # vertical

    world.run()


if __name__ == "__main__":
    main()
