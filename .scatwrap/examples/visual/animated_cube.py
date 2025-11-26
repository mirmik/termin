<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/animated_cube.py</title>
</head>
<body>
<pre><code>
&quot;&quot;&quot;Animated cube demo: simple rotation driven by a custom component.&quot;&quot;&quot;

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
    Component,
)
from termin.visualization.components import MeshRenderer
from termin.visualization.shader import ShaderProgram
from termin.visualization.skybox import SkyBoxEntity
from termin.visualization.camera import CameraController

VERT = &quot;&quot;&quot;
#version 330 core
layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_normal;
out vec3 v_world_pos;

void main() {
    vec4 world = u_model * vec4(a_position, 1.0);
    v_world_pos = world.xyz;
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;
    gl_Position = u_projection * u_view * world;
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


class RotateComponent(Component):
    &quot;&quot;&quot;Simple component that rotates its entity around a fixed axis.&quot;&quot;&quot;

    def __init__(self, axis: np.ndarray = np.array([0.0, 1.0, 0.0]), speed: float = 1.0):
        super().__init__(enabled=True)
        axis = np.asarray(axis, dtype=float)
        norm = np.linalg.norm(axis)
        self.axis = axis / norm if norm &gt; 0 else np.array([0.0, 1.0, 0.0])
        self.speed = speed
        self.angle = 0.0

    def update(self, dt: float):
        if self.entity is None:
            return
        self.angle += self.speed * dt
        rot_pose = Pose3.rotation(self.axis, self.angle)
        translation = self.entity.transform.global_pose().lin.copy()
        self.entity.transform.relocate(Pose3(ang=rot_pose.ang.copy(), lin=translation))


def build_scene(world: VisualizationWorld) -&gt; tuple[Scene, PerspectiveCameraComponent]:
    mesh = MeshDrawable(CubeMesh(size=1.0))
    shader = ShaderProgram(VERT, FRAG)
    material = Material(shader=shader, color=np.array([0.3, 0.7, 0.9, 1.0], dtype=np.float32))

    cube = Entity(pose=Pose3.identity(), name=&quot;cube&quot;)
    cube.add_component(MeshRenderer(mesh, material))
    cube.add_component(RotateComponent(axis=np.array([0.2, 1.0, 0.3]), speed=1.5))

    scene = Scene()
    scene.add(cube)
    scene.add(SkyBoxEntity())
    world.add_scene(scene)

    camera_entity = Entity(name=&quot;camera&quot;)
    camera = PerspectiveCameraComponent()
    camera_entity.add_component(camera)
    camera_entity.add_component(OrbitCameraController(radius=5.0, elevation=30.0))
    scene.add(camera_entity)

    return scene, camera


def main():
    world = VisualizationWorld()
    scene, camera = build_scene(world)
    window = world.create_window(title=&quot;termin animated cube&quot;)
    window.add_viewport(scene, camera)
    world.run()


if __name__ == &quot;__main__&quot;:
    main()

</code></pre>
</body>
</html>
