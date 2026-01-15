"""Demonstrate 3D scene with a UI canvas overlay."""

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
from termin.visualization.ui import Canvas, UIRectangle


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

void main() {
    vec3 N = normalize(v_normal);
    float ndotl = max(dot(N, -normalize(u_light_dir)), 0.0);
    vec3 color = u_color.rgb * (0.2 + 0.8 * ndotl);
    FragColor = vec4(color, u_color.a);
}
"""

"""Standard UI shader sources (position + optional texturing)."""

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
        // При включённой текстуре берём альфа-канал из красного канала атласа
        alpha *= texture(u_texture, v_uv).r;
    }
    FragColor = vec4(u_color.rgb, alpha);
}
"""



def build_scene(world: VisualizationWorld) -> tuple[Scene, PerspectiveCameraComponent, Canvas]:
    shader = TcShader.from_sources(VERT, FRAG, "", "UIOverlaySceneShader")
    material = Material(shader=shader, color=np.array([0.6, 0.8, 0.9, 1.0], dtype=np.float32))
    mesh = MeshDrawable(CubeMesh(size=1.5))
    cube = Entity(name="cube", pose=Pose3.identity())
    cube.add_component(MeshRenderer(mesh, material))

    scene = Scene()
    scene.add(cube)
    world.add_scene(scene)

    cam_entity = Entity(name="camera")
    camera = PerspectiveCameraComponent()
    cam_entity.add_component(camera)
    cam_entity.add_component(OrbitCameraController(radius=5.0))
    scene.add(cam_entity)

    canvas = Canvas()
    ui_shader = TcShader.from_sources(UI_VERTEX_SHADER, UI_FRAGMENT_SHADER, "", "UIOverlayShader")
    ui_material = Material(shader=ui_shader, color=np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32), uniforms={"u_use_texture": False})
    canvas.add(UIRectangle(position=(0.05, 0.05), size=(0.25, 0.1), color=(0.1, 0.1, 0.1, 0.7), material=ui_material))
    canvas.add(UIRectangle(position=(0.07, 0.07), size=(0.21, 0.06), color=(0.9, 0.4, 0.2, 1.0), material=ui_material))

    return scene, camera, canvas


def main():
    world = VisualizationWorld()
    scene, camera, canvas = build_scene(world)
    window = world.create_window(title="termin UI overlay")
    window.add_viewport(scene, camera, canvas=canvas)
    world.run()


if __name__ == "__main__":
    main()
