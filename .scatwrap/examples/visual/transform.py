<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/transform.py</title>
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
    Entity,<br>
    MeshDrawable,<br>
    Scene,<br>
    Material,<br>
    Texture,<br>
    VisualizationWorld,<br>
    PerspectiveCameraComponent,<br>
    OrbitCameraController,<br>
)<br>
from termin.visualization.components import MeshRenderer<br>
from termin.visualization.shader import ShaderProgram<br>
from termin.visualization.skybox import SkyBoxEntity<br>
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
    vec4 world = u_model * vec4(a_position, 1.0);<br>
    v_world_pos = world.xyz;<br>
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;<br>
    v_texcoord = a_texcoord;<br>
    gl_Position = u_projection * u_view * world;<br>
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
    vec3 N = normalize(v_normal);<br>
    vec3 L = normalize(-u_light_dir);<br>
    vec3 V = normalize(u_view_pos - v_world_pos);<br>
    vec3 texColor = texture(u_diffuse_map, v_texcoord).rgb;<br>
    float ndotl = max(dot(N, L), 0.0);<br>
    vec3 diffuse = texColor * ndotl;<br>
    vec3 ambient = texColor * 0.2;<br>
    vec3 H = normalize(L + V);<br>
    float spec = pow(max(dot(N, H), 0.0), 32.0);<br>
    vec3 specular = vec3(0.4) * spec;<br>
    vec3 color = (ambient + diffuse) * u_light_color + specular;<br>
    FragColor = vec4(color, 1.0);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
def build_scene(world: VisualizationWorld) -&gt; tuple[Scene, PerspectiveCameraComponent]:<br>
    texture_path = &quot;examples/data/textures/crate_diffuse.png&quot;<br>
    texture = Texture.from_file(texture_path)<br>
    mesh = TexturedCubeMesh()<br>
    drawable = MeshDrawable(mesh)<br>
    shader_prog = ShaderProgram(VERT, FRAG)<br>
    material = Material(shader=shader_prog, color=None, textures={&quot;u_diffuse_map&quot;: texture})<br>
<br>
    cube1 = Entity(pose=Pose3.identity(), name=&quot;cube&quot;)<br>
    cube1.add_component(MeshRenderer(drawable, material))<br>
    cube1.transform.relocate(Pose3(lin=np.array([-2.0, 0.0, 0.0])))<br>
<br>
    cube2 = Entity(pose=Pose3.identity(), name=&quot;cube&quot;)<br>
    cube2.add_component(MeshRenderer(drawable, material))<br>
    cube2.transform.relocate(Pose3(lin= np.array([0.0, 0.0, 1.0])))<br>
    cube2.transform.set_parent(cube1.transform)<br>
<br>
    scene = Scene()<br>
    scene.add(cube1)<br>
    scene.add(cube2)<br>
    scene.add(SkyBoxEntity())<br>
    world.add_scene(scene)<br>
<br>
    camera_entity = Entity(name=&quot;camera&quot;)<br>
    camera = PerspectiveCameraComponent()<br>
    camera_entity.add_component(camera)<br>
    camera_entity.add_component(OrbitCameraController())<br>
    scene.add(camera_entity)<br>
<br>
    return scene, camera<br>
<br>
<br>
def main():<br>
    world = VisualizationWorld()<br>
    scene, camera = build_scene(world)<br>
    window = world.create_window(title=&quot;termin textured cube&quot;)<br>
    window.add_viewport(scene, camera)<br>
    world.run()<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
    main()<br>
<!-- END SCAT CODE -->
</body>
</html>
