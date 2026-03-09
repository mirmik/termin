"""Demo of the widget-based UI system with YAML loading."""

from __future__ import annotations

import numpy as np

from termin.geombase import Pose3
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
from tgfx import TcShader
from tcgui.widgets import UIComponent, Button
from tcgui.font import FontTextureAtlas


# 3D shader
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


def build_scene(world: VisualizationWorld):
    # 3D cube
    shader = TcShader.from_sources(VERT, FRAG, "", "UIWidgetYamlShader")
    material = Material(shader=shader, color=np.array([0.6, 0.8, 0.9, 1.0], dtype=np.float32))
    cube_mesh = MeshDrawable(CubeMesh(size=1.0))

    cube = Entity(name="cube", pose=Pose3.identity())
    cube.add_component(MeshRenderer(cube_mesh, material))

    scene = Scene()
    scene.add(cube)
    world.add_scene(scene)

    # Camera + orbit controller
    cam_entity = Entity(name="camera")
    cam = PerspectiveCameraComponent()
    cam_entity.add_component(cam)
    cam_entity.add_component(OrbitCameraController(radius=5.0))
    scene.add(cam_entity)

    # --- UI via UIComponent with YAML ---
    ui_entity = Entity(name="ui")
    ui_comp = UIComponent(priority=0)

    # Load font
    ui_comp.font = FontTextureAtlas("examples/data/fonts/Roboto-Regular.ttf", size=32)

    # Load UI from YAML file
    ui_comp.load("examples/data/ui/demo_menu.yaml")

    # Connect button handlers after loading
    click_count = [0]
    info_label = ui_comp.find("info_label")

    def on_click():
        click_count[0] += 1
        if info_label:
            info_label.text = f"Click count: {click_count[0]}"
        print(f"Button clicked! Count: {click_count[0]}")

    def on_reset():
        click_count[0] = 0
        if info_label:
            info_label.text = "Click count: 0"
        print("Counter reset!")

    click_btn = ui_comp.find("click_button")
    if click_btn and isinstance(click_btn, Button):
        click_btn.on_click = on_click

    reset_btn = ui_comp.find("reset_button")
    if reset_btn and isinstance(reset_btn, Button):
        reset_btn.on_click = on_reset

    ui_entity.add_component(ui_comp)
    scene.add(ui_entity)

    return scene, cam


def main():
    world = VisualizationWorld()
    scene, cam = build_scene(world)

    win = world.create_window(title="Widget UI YAML Demo")
    win.add_viewport(scene, cam)

    world.run()


if __name__ == "__main__":
    main()
