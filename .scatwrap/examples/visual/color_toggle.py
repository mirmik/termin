<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/color_toggle.py</title>
</head>
<body>
<pre><code>
&quot;&quot;&quot;Example: change cube color when SPACE is pressed.&quot;&quot;&quot;

from __future__ import annotations

import numpy as np
from termin.mesh.mesh import CubeMesh
from termin.visualization import (
    Entity,
    MeshDrawable,
    Scene,
    Material,
    VisualizationWorld,
    PerspectiveCameraComponent,
    OrbitCameraController,
    InputComponent,
)
from termin.visualization.backends.base import Action, Key
from termin.visualization.components import MeshRenderer
from termin.visualization.shader import ShaderProgram
from termin.visualization.skybox import SkyBoxEntity


VERT = &quot;&quot;&quot;
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
&quot;&quot;&quot;

FRAG = &quot;&quot;&quot;
#version 330 core
in vec3 v_normal;
uniform vec4 u_color;

out vec4 FragColor;

void main() {
    vec3 n = normalize(v_normal);
    float ndotl = max(dot(n, vec3(0.3, 0.7, 0.4)), 0.0);
    vec3 color = u_color.rgb * (0.2 + 0.8 * ndotl);
    FragColor = vec4(color, u_color.a);
}
&quot;&quot;&quot;


class ColorToggleComponent(InputComponent):
    &quot;&quot;&quot;Toggle material color when the user presses space.&quot;&quot;&quot;

    def __init__(self, material: Material, colors: list[np.ndarray]):
        super().__init__(enabled=True)
        self.material = material
        self.colors = colors
        self.index = 0

    def on_key(self, viewport, key: int, scancode: int, action: int, mods: int):
        if key == Key.SPACE and action == Action.PRESS:
            self.index = (self.index + 1) % len(self.colors)
            self.material.update_color(self.colors[self.index])


def build_scene(world: VisualizationWorld) -&gt; tuple[Scene, PerspectiveCameraComponent]:
    shader = ShaderProgram(VERT, FRAG)
    material = Material(shader=shader, color=np.array([0.9, 0.2, 0.2, 1.0], dtype=np.float32))
    mesh = MeshDrawable(CubeMesh(size=1.5))
    cube = Entity(name=&quot;cube&quot;)
    cube.add_component(MeshRenderer(mesh, material))
    cube.add_component(
        ColorToggleComponent(
            material,
            [
                np.array([0.9, 0.2, 0.2, 1.0]),
                np.array([0.2, 0.9, 0.3, 1.0]),
                np.array([0.2, 0.4, 0.9, 1.0]),
            ],
        )
    )

    scene = Scene()
    scene.add(cube)
    scene.add(SkyBoxEntity())
    world.add_scene(scene)

    cam_entity = Entity(name=&quot;camera&quot;)
    camera = PerspectiveCameraComponent()
    cam_entity.add_component(camera)
    cam_entity.add_component(OrbitCameraController(radius=4.0))
    scene.add(cam_entity)
    return scene, camera


def main():
    world = VisualizationWorld()
    scene, camera = build_scene(world)
    window = world.create_window(title=&quot;termin color toggle&quot;)
    window.add_viewport(scene, camera)
    world.run()


if __name__ == &quot;__main__&quot;:
    main()

</code></pre>
</body>
</html>
