"""Demo of the widget-based UI system with UIComponent."""

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
from termin._native.render import TcShader
from termin.visualization.ui.widgets import (
    UIComponent,
    Panel,
    VStack,
    HStack,
    Label,
    Button,
    Separator,
    px,
    pct,
)
from termin.visualization.ui.font import FontTextureAtlas


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
    shader = TcShader.from_sources(VERT, FRAG, "", "UIWidgetDemoShader")
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

    # --- UI via UIComponent ---
    ui_entity = Entity(name="ui")
    ui_comp = UIComponent(priority=0)

    # Load font
    ui_comp.font = FontTextureAtlas("examples/data/fonts/Roboto-Regular.ttf", size=32)

    # Build UI programmatically
    panel = Panel()
    panel.name = "main_panel"
    panel.padding = 15
    panel.background_color = (0.1, 0.1, 0.15, 0.9)
    panel.border_radius = 8
    panel.preferred_width = px(250)

    stack = VStack()
    stack.spacing = 10
    stack.alignment = "left"

    # Title
    title = Label()
    title.text = "Widget UI Demo"
    title.font_size = 20
    title.color = (1, 1, 1, 1)
    stack.add_child(title)

    # Separator
    sep = Separator()
    sep.orientation = "horizontal"
    sep.color = (0.5, 0.5, 0.5, 0.5)
    stack.add_child(sep)

    # Info label
    info = Label()
    info.name = "info_label"
    info.text = "Click count: 0"
    info.font_size = 14
    info.color = (0.8, 0.8, 0.8, 1)
    stack.add_child(info)

    # Button row
    btn_row = HStack()
    btn_row.spacing = 10

    click_count = [0]

    def on_click():
        click_count[0] += 1
        info.text = f"Click count: {click_count[0]}"
        print(f"Button clicked! Count: {click_count[0]}")

    btn = Button()
    btn.name = "click_button"
    btn.text = "Click me!"
    btn.font_size = 14
    btn.padding = 12
    btn.background_color = (0.2, 0.5, 0.8, 1)
    btn.hover_color = (0.3, 0.6, 0.9, 1)
    btn.pressed_color = (0.1, 0.4, 0.7, 1)
    btn.on_click = on_click
    btn_row.add_child(btn)

    reset_btn = Button()
    reset_btn.text = "Reset"
    reset_btn.font_size = 14
    reset_btn.padding = 12
    reset_btn.background_color = (0.5, 0.2, 0.2, 1)
    reset_btn.hover_color = (0.6, 0.3, 0.3, 1)
    reset_btn.pressed_color = (0.4, 0.1, 0.1, 1)
    reset_btn.on_click = lambda: (click_count.__setitem__(0, 0), info.__setattr__("text", "Click count: 0"))
    btn_row.add_child(reset_btn)

    stack.add_child(btn_row)
    panel.add_child(stack)

    ui_comp.root = panel
    ui_entity.add_component(ui_comp)
    scene.add(ui_entity)

    return scene, cam


def main():
    world = VisualizationWorld()
    scene, cam = build_scene(world)

    win = world.create_window(title="Widget UI Demo")
    win.add_viewport(scene, cam)

    world.run()


if __name__ == "__main__":
    main()
