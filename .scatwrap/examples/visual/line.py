<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/line.py</title>
</head>
<body>
<pre><code>
&quot;&quot;&quot;Line rendering demo with multiple viewports.&quot;&quot;&quot;

from __future__ import annotations

import numpy as np

from termin.visualization import (
    Entity,
    Material,
    Scene,
    VisualizationWorld,
    PerspectiveCameraComponent,
    OrbitCameraController,
)
from termin.visualization.line import LineEntity
from termin.visualization.shader import ShaderProgram


VERT = &quot;&quot;&quot;
#version 330 core
layout(location = 0) in vec3 a_position;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

void main() {
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
&quot;&quot;&quot;


FRAG = &quot;&quot;&quot;
#version 330 core
uniform vec4 u_color;
out vec4 FragColor;

void main() {
    FragColor = u_color;
}
&quot;&quot;&quot;


def build_scene(world: VisualizationWorld) -&gt; tuple[Scene, PerspectiveCameraComponent]:
    shader_prog = ShaderProgram(VERT, FRAG)
    material = Material(shader=shader_prog, color=np.array([0.1, 0.8, 0.2, 1.0], dtype=np.float32))
    points = [
        np.array([0.0, 0.0, 0.0]),
        np.array([1.0, 0.0, 0.0]),
        np.array([1.0, 1.0, 0.0]),
        np.array([0.0, 1.0, 0.0]),
        np.array([0.0, 0.0, 0.0]),
    ]
    line1 = LineEntity(points=points, material=material, name=&quot;line1&quot;)
    line2 = LineEntity(points=[p + np.array([0.0, 0.0, 1.0]) for p in points], material=material, name=&quot;line2&quot;)

    scene = Scene()
    scene.add(line1)
    scene.add(line2)
    world.add_scene(scene)

    camera_entity = Entity(name=&quot;camera&quot;)
    camera = PerspectiveCameraComponent()
    camera_entity.add_component(camera)
    camera_entity.add_component(OrbitCameraController(target=np.array([0.5, 0.5, 0.5])))
    scene.add(camera_entity)

    return scene, camera


def main():
    world = VisualizationWorld()
    scene, camera = build_scene(world)
    window = world.create_window(title=&quot;termin line demo&quot;)
    # illustrate two viewports referencing same scene/camera
    window.add_viewport(scene, camera, rect=(0.0, 0.0, 0.5, 1.0))
    window.add_viewport(scene, camera, rect=(0.5, 0.0, 0.5, 1.0))
    world.run()


if __name__ == &quot;__main__&quot;:
    main()

</code></pre>
</body>
</html>
