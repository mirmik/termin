"""Widget-based UI demo: YAML-loaded toolbar over 3D scene."""

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
from termin.visualization.ui.font import FontTextureAtlas
from termin.visualization.ui.widgets import UI, Button


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


# Global state for demo
current_mode = "shaded"


def build_scene(world: VisualizationWorld):
    # 3D cube
    shader = TcShader.from_sources(VERT, FRAG, "", "UIWidgetsShader")
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

    return scene, cam


def main():
    global current_mode

    world = VisualizationWorld()
    scene, cam = build_scene(world)

    win = world.create_window(title="termin UI Widgets")
    win.add_viewport(scene, cam)

    # Create UI after window (need graphics backend)
    graphics = win.graphics
    font = FontTextureAtlas("examples/data/fonts/Roboto-Regular.ttf", size=24)

    ui = UI(graphics, font)

    # Load toolbar from YAML
    ui.load("examples/data/ui/toolbar.yaml")

    # Bind button callbacks
    def set_mode(mode: str):
        global current_mode
        current_mode = mode
        print(f">>> Mode changed to: {mode}")

    btn_wireframe = ui.find("btn_wireframe")
    if isinstance(btn_wireframe, Button):
        btn_wireframe.on_click = lambda: set_mode("wireframe")

    btn_shaded = ui.find("btn_shaded")
    if isinstance(btn_shaded, Button):
        btn_shaded.on_click = lambda: set_mode("shaded")

    btn_textured = ui.find("btn_textured")
    if isinstance(btn_textured, Button):
        btn_textured.on_click = lambda: set_mode("textured")

    btn_play = ui.find("btn_play")
    if isinstance(btn_play, Button):
        btn_play.on_click = lambda: print(">>> Play clicked!")

    # Store UI in window for rendering
    # Note: This is a demo - proper integration would add UI to the render loop
    win._demo_ui = ui

    print("UI Widgets Demo")
    print("Toolbar loaded from YAML with buttons: Wireframe, Shaded, Textured, Play")
    print("Click buttons to see mode changes in console")

    world.run()


if __name__ == "__main__":
    main()
