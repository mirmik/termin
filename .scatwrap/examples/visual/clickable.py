<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/clickable.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Textured cube demo using the component-based visualization world.&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
import numpy as np<br>
<br>
from termin.geombase.pose3 import Pose3<br>
from termin.mesh.mesh import TexturedCubeMesh<br>
from termin.visualization import (<br>
&#9;Entity,<br>
&#9;MeshDrawable,<br>
&#9;Scene,<br>
&#9;Material,<br>
&#9;Texture,<br>
&#9;VisualizationWorld,<br>
&#9;PerspectiveCameraComponent,<br>
&#9;OrbitCameraController,<br>
)<br>
from termin.visualization.entity import Entity, Component<br>
from termin.visualization.components import MeshRenderer<br>
from termin.visualization.shader import ShaderProgram<br>
from termin.visualization.skybox import SkyBoxEntity<br>
from termin.colliders.box import BoxCollider<br>
from termin.colliders.collider_component import ColliderComponent<br>
<br>
# === воображаемый интерфейс кликабельности ===<br>
class Clickable:<br>
&#9;def on_click(self, hit, button: int):<br>
&#9;&#9;pass<br>
<br>
# === простой обработчик клика ===<br>
class CubeClickHandler(Component, Clickable):<br>
&#9;def __init__(self, name: str):<br>
&#9;&#9;self.name = name<br>
&#9;&#9;super().__init__()<br>
<br>
&#9;def on_click(self, hit, button: int):<br>
&#9;&#9;print(f&quot;Клик по кубу '{self.name}', точка: {hit.point}&quot;)<br>
<br>
<br>
VERT = &quot;&quot;&quot;<br>
#version 330 core<br>
layout(location = 0) in vec3 a_position;<br>
layout(location = 1) in vec3 a_normal;<br>
layout(location = 2) in vec2 a_texcoord;<br>
<br>
uniform mat4 u_model;<br>
uniform mat4 u_view;<br>
uniform mat4 u_projection;<br>
<br>
out vec3 v_normal;<br>
out vec3 v_world_pos;<br>
out vec2 v_texcoord;<br>
<br>
void main() {<br>
&#9;vec4 world = u_model * vec4(a_position, 1.0);<br>
&#9;v_world_pos = world.xyz;<br>
&#9;v_normal = mat3(transpose(inverse(u_model))) * a_normal;<br>
&#9;v_texcoord = a_texcoord;<br>
&#9;gl_Position = u_projection * u_view * world;<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
FRAG = &quot;&quot;&quot;<br>
#version 330 core<br>
in vec3 v_normal;<br>
in vec3 v_world_pos;<br>
in vec2 v_texcoord;<br>
<br>
uniform vec3 u_light_dir;<br>
uniform vec3 u_light_color;<br>
uniform vec3 u_view_pos;<br>
uniform sampler2D u_diffuse_map;<br>
<br>
out vec4 FragColor;<br>
<br>
void main() {<br>
&#9;vec3 N = normalize(v_normal);<br>
&#9;vec3 L = normalize(-u_light_dir);<br>
&#9;vec3 V = normalize(u_view_pos - v_world_pos);<br>
&#9;vec3 texColor = texture(u_diffuse_map, v_texcoord).rgb;<br>
&#9;float ndotl = max(dot(N, L), 0.0);<br>
&#9;vec3 diffuse = texColor * ndotl;<br>
&#9;vec3 ambient = texColor * 0.2;<br>
&#9;vec3 H = normalize(L + V);<br>
&#9;float spec = pow(max(dot(N, H), 0.0), 32.0);<br>
&#9;vec3 specular = vec3(0.4) * spec;<br>
&#9;vec3 color = (ambient + diffuse) * u_light_color + specular;<br>
&#9;FragColor = vec4(color, 1.0);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
def build_scene(world: VisualizationWorld) -&gt; tuple[Scene, PerspectiveCameraComponent]:<br>
&#9;texture_path = &quot;examples/data/textures/crate_diffuse.png&quot;<br>
&#9;texture = Texture.from_file(texture_path)<br>
&#9;mesh = TexturedCubeMesh()<br>
&#9;drawable = MeshDrawable(mesh)<br>
&#9;shader_prog = ShaderProgram(VERT, FRAG)<br>
&#9;material = Material(shader=shader_prog, color=None, textures={&quot;u_diffuse_map&quot;: texture})<br>
<br>
&#9;# Первый куб<br>
&#9;cube1 = Entity(pose=Pose3.identity(), name=&quot;cube_1&quot;)<br>
&#9;cube1.add_component(MeshRenderer(drawable, material))<br>
&#9;cube1.add_component(CubeClickHandler(&quot;cube_1&quot;))<br>
&#9;cube1.add_component(ColliderComponent(BoxCollider(size=np.array([1.0, 1.0, 1.0]))))<br>
&#9;cube1.transform.relocate(Pose3(lin=np.array([-2.0, 0.0, 0.0])))<br>
<br>
&#9;# Второй куб<br>
&#9;cube2 = Entity(pose=Pose3.identity(), name=&quot;cube_2&quot;)<br>
&#9;cube2.add_component(MeshRenderer(drawable, material))<br>
&#9;cube2.add_component(CubeClickHandler(&quot;cube_2&quot;))<br>
&#9;cube2.add_component(ColliderComponent(BoxCollider(size=np.array([1.0, 1.0, 1.0]))))<br>
&#9;cube2.transform.relocate(Pose3(lin=np.array([0.0, 0.0, 1.0])))<br>
&#9;cube2.transform.set_parent(cube1.transform)<br>
<br>
&#9;scene = Scene()<br>
&#9;scene.add(cube1)<br>
&#9;scene.add(cube2)<br>
&#9;scene.add(SkyBoxEntity())<br>
&#9;world.add_scene(scene)<br>
<br>
&#9;camera_entity = Entity(name=&quot;camera&quot;)<br>
&#9;camera = PerspectiveCameraComponent()<br>
&#9;camera_entity.add_component(camera)<br>
&#9;camera_entity.add_component(OrbitCameraController())<br>
&#9;scene.add(camera_entity)<br>
<br>
&#9;return scene, camera<br>
<br>
<br>
def main():<br>
&#9;world = VisualizationWorld()<br>
&#9;scene, camera = build_scene(world)<br>
&#9;window = world.create_window(title=&quot;termin textured cube&quot;)<br>
&#9;window.add_viewport(scene, camera)<br>
&#9;world.run()<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
&#9;main()<br>
<!-- END SCAT CODE -->
</body>
</html>
