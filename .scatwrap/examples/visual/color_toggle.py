<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/color_toggle.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Example: change cube color when SPACE is pressed.&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
import numpy as np<br>
from termin.mesh.mesh import CubeMesh<br>
from termin.visualization import (<br>
    Entity,<br>
    MeshDrawable,<br>
    Scene,<br>
    Material,<br>
    VisualizationWorld,<br>
    PerspectiveCameraComponent,<br>
    OrbitCameraController,<br>
    InputComponent,<br>
)<br>
from termin.visualization.backends.base import Action, Key<br>
from termin.visualization.components import MeshRenderer<br>
from termin.visualization.shader import ShaderProgram<br>
from termin.visualization.skybox import SkyBoxEntity<br>
<br>
<br>
VERT = &quot;&quot;&quot;<br>
#version 330 core<br>
layout(location = 0) in vec3 a_position;<br>
layout(location = 1) in vec3 a_normal;<br>
<br>
uniform mat4 u_model;<br>
uniform mat4 u_view;<br>
uniform mat4 u_projection;<br>
<br>
out vec3 v_normal;<br>
<br>
void main() {<br>
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;<br>
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
FRAG = &quot;&quot;&quot;<br>
#version 330 core<br>
in vec3 v_normal;<br>
uniform vec4 u_color;<br>
<br>
out vec4 FragColor;<br>
<br>
void main() {<br>
    vec3 n = normalize(v_normal);<br>
    float ndotl = max(dot(n, vec3(0.3, 0.7, 0.4)), 0.0);<br>
    vec3 color = u_color.rgb * (0.2 + 0.8 * ndotl);<br>
    FragColor = vec4(color, u_color.a);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
class ColorToggleComponent(InputComponent):<br>
    &quot;&quot;&quot;Toggle material color when the user presses space.&quot;&quot;&quot;<br>
<br>
    def __init__(self, material: Material, colors: list[np.ndarray]):<br>
        super().__init__(enabled=True)<br>
        self.material = material<br>
        self.colors = colors<br>
        self.index = 0<br>
<br>
    def on_key(self, viewport, key: int, scancode: int, action: int, mods: int):<br>
        if key == Key.SPACE and action == Action.PRESS:<br>
            self.index = (self.index + 1) % len(self.colors)<br>
            self.material.update_color(self.colors[self.index])<br>
<br>
<br>
def build_scene(world: VisualizationWorld) -&gt; tuple[Scene, PerspectiveCameraComponent]:<br>
    shader = ShaderProgram(VERT, FRAG)<br>
    material = Material(shader=shader, color=np.array([0.9, 0.2, 0.2, 1.0], dtype=np.float32))<br>
    mesh = MeshDrawable(CubeMesh(size=1.5))<br>
    cube = Entity(name=&quot;cube&quot;)<br>
    cube.add_component(MeshRenderer(mesh, material))<br>
    cube.add_component(<br>
        ColorToggleComponent(<br>
            material,<br>
            [<br>
                np.array([0.9, 0.2, 0.2, 1.0]),<br>
                np.array([0.2, 0.9, 0.3, 1.0]),<br>
                np.array([0.2, 0.4, 0.9, 1.0]),<br>
            ],<br>
        )<br>
    )<br>
<br>
    scene = Scene()<br>
    scene.add(cube)<br>
    scene.add(SkyBoxEntity())<br>
    world.add_scene(scene)<br>
<br>
    cam_entity = Entity(name=&quot;camera&quot;)<br>
    camera = PerspectiveCameraComponent()<br>
    cam_entity.add_component(camera)<br>
    cam_entity.add_component(OrbitCameraController(radius=4.0))<br>
    scene.add(cam_entity)<br>
    return scene, camera<br>
<br>
<br>
def main():<br>
    world = VisualizationWorld()<br>
    scene, camera = build_scene(world)<br>
    window = world.create_window(title=&quot;termin color toggle&quot;)<br>
    window.add_viewport(scene, camera)<br>
    world.run()<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
    main()<br>
<!-- END SCAT CODE -->
</body>
</html>
