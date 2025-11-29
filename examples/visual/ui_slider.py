"""UI slider demo: draggable slider controlling cube color."""

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
from termin.visualization.render.components import MeshRenderer
from termin.visualization.render.shader import ShaderProgram
from termin.visualization.render.skybox import SkyBoxEntity

from termin.visualization.ui import Canvas, UIRectangle
from termin.visualization.ui.font import FontTextureAtlas
from termin.visualization.ui.elements import UISlider, UIText


# ----- 3D SHADER ---------------------------------------------------

VERT = """
#version 330 core
layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_normal;

void main() {
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""

FRAG = """
#version 330 core
in vec3 v_normal;
uniform vec4 u_color;
uniform vec3 u_light_dir;
out vec4 FragColor;

void main(){
    vec3 N = normalize(v_normal);
    float ndotl = max(dot(N, -normalize(u_light_dir)), 0.0);
    vec3 color = u_color.rgb * (0.2 + 0.8 * ndotl);
    FragColor = vec4(color, u_color.a);
}
"""


# ----- UI SHADER ---------------------------------------------------

UI_VERTEX_SHADER = """
#version 330 core
layout(location=0) in vec2 a_position;
layout(location=1) in vec2 a_uv;

out vec2 v_uv;

void main(){
    v_uv = a_uv;
    gl_Position = vec4(a_position, 0, 1);
}
"""

UI_FRAGMENT_SHADER = """
#version 330 core
uniform sampler2D u_texture;
uniform vec4 u_color;
uniform bool u_use_texture;

in vec2 v_uv;
out vec4 FragColor;

void main(){
    float alpha = u_color.a;
    if (u_use_texture) {
        alpha *= texture(u_texture, v_uv).r;
    }
    FragColor = vec4(u_color.rgb, alpha);
}
"""


# ----- BUILD SCENE ---------------------------------------------------

def build_scene(world: VisualizationWorld):
    # 3D cube
    shader = ShaderProgram(VERT, FRAG)
    cube_color = np.array([0.6, 0.8, 0.9, 1.0], dtype=np.float32)
    material = Material(shader=shader, color=cube_color)
    cube_mesh = MeshDrawable(CubeMesh(size=1.0))

    cube = Entity(name="cube", pose=Pose3.identity())
    cube.add_component(MeshRenderer(cube_mesh, material))

    scene = Scene()
    scene.add(cube)
    scene.add(SkyBoxEntity())
    world.add_scene(scene)

    # Camera + orbit controller
    cam_entity = Entity(name="camera")
    cam = PerspectiveCameraComponent()
    cam_entity.add_component(cam)
    cam_entity.add_component(OrbitCameraController(radius=5.0))
    scene.add(cam_entity)

    # ----- UI CANVAS -----
    canvas = Canvas()

    # UI materials
    ui_shader = ShaderProgram(UI_VERTEX_SHADER, UI_FRAGMENT_SHADER)
    ui_material_rect = Material(
        ui_shader,
        color=np.array([1, 1, 1, 1], dtype=np.float32),
        uniforms={"u_use_texture": False}
    )
    ui_material_text = Material(
        ui_shader,
        color=np.array([1, 1, 1, 1], dtype=np.float32),
        uniforms={"u_use_texture": True}
    )

    # Font for text and slider label
    canvas.font = FontTextureAtlas("examples/data/fonts/Roboto-Regular.ttf", size=32)

    # Background panel
    canvas.add(UIRectangle(
        position=(0.04, 0.04),
        size=(0.50, 0.20),
        color=(0, 0, 0, 0.4),
        material=ui_material_rect,
    ))

    # Label above slider
    canvas.add(UIText(
        text="Cube color (blue component):",
        position=(0.05, 0.05),
        color=(1, 1, 1, 1),
        material=ui_material_text,
        scale=0.8,
    ))

    # ----- SLIDER -----
    def on_slider(value: float):
        # value 0..1 → меняем кубовый цвет
        cube_color[2] = value  # blue channel
        material.update_color(cube_color)

    slider = UISlider(
        position=(0.05, 0.10),
        size=(0.40, 0.06),
        value=0.9,
        on_change=on_slider,
        material=ui_material_rect,        # track material
        handle_material=ui_material_rect  # handle material
    )
    canvas.add(slider)

    return scene, cam, canvas


# ----- MAIN -----------------------------------------------------------

def main():
    world = VisualizationWorld()
    scene, cam, canvas = build_scene(world)

    win = world.create_window(title="termin UI slider demo")
    win.add_viewport(scene, cam, canvas=canvas)

    world.run()


if __name__ == "__main__":
    main()
