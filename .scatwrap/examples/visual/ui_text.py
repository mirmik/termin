<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/ui_text.py</title>
</head>
<body>
<pre><code>
&quot;&quot;&quot;Text rendering demo: UI text overlay on a 3D scene.&quot;&quot;&quot;

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
from termin.visualization.components import MeshRenderer
from termin.visualization.shader import ShaderProgram
from termin.visualization.skybox import SkyBoxEntity
from termin.visualization.ui import Canvas, UIRectangle
from termin.visualization.ui.elements import UIText
from termin.visualization.ui.font import FontTextureAtlas


VERT = &quot;&quot;&quot;
#version 330 core
layout(location=0) in vec3 a_position;
layout(location=1) in vec3 a_normal;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_normal;

void main() {
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
&quot;&quot;&quot;

FRAG = &quot;&quot;&quot;
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
&quot;&quot;&quot;

&quot;&quot;&quot;Standard UI shader sources (position + optional texturing).&quot;&quot;&quot;

UI_VERTEX_SHADER = &quot;&quot;&quot;
#version 330 core
layout(location=0) in vec2 a_position;
layout(location=1) in vec2 a_uv;

out vec2 v_uv;

void main(){
    v_uv = a_uv;
    gl_Position = vec4(a_position, 0, 1);
}
&quot;&quot;&quot;

UI_FRAGMENT_SHADER = &quot;&quot;&quot;
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
&quot;&quot;&quot;



def build_scene(world: VisualizationWorld):
    shader = ShaderProgram(VERT, FRAG)
    mat = Material(shader=shader, color=np.array([0.7, 0.4, 0.2, 1.0]))
    mesh = MeshDrawable(CubeMesh())
    cube = Entity(pose=Pose3.identity(), name=&quot;cube&quot;)
    cube.add_component(MeshRenderer(mesh, mat))

    scene = Scene()
    scene.add(cube)
    scene.add(SkyBoxEntity())
    world.add_scene(scene)

    cam_e = Entity(name=&quot;camera&quot;)
    cam = PerspectiveCameraComponent()
    cam_e.add_component(cam)
    cam_e.add_component(OrbitCameraController(radius=5.0))
    scene.add(cam_e)

    canvas = Canvas()
    ui_shader = ShaderProgram(UI_VERTEX_SHADER, UI_FRAGMENT_SHADER)
    rect_material = Material(shader=ui_shader, color=np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32), uniforms={&quot;u_use_texture&quot;: False})
    text_material = Material(shader=ui_shader, color=np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32), uniforms={&quot;u_use_texture&quot;: True})

    canvas.add(UIRectangle(position=(0.05, 0.05), size=(0.3, 0.1), color=(0, 0, 0, 0.5), material=rect_material))

    canvas.font = FontTextureAtlas(&quot;examples/data/fonts/Roboto-Regular.ttf&quot;, size=32)
    canvas.add(UIText(&quot;Hello, world!&quot;, position=(0.07, 0.07), color=(1, 1, 1, 1), scale=1.0, material=text_material))

    return scene, cam, canvas


def main():
    world = VisualizationWorld()
    scene, cam, canvas = build_scene(world)
    win = world.create_window(title=&quot;termin UI text&quot;)
    win.add_viewport(scene, cam, canvas=canvas)
    world.run()


if __name__ == &quot;__main__&quot;:
    main()

</code></pre>
</body>
</html>
