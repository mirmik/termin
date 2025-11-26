<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/text_cube_gray_blur.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;<br>
Textured cube demo + grayscale + Gaussian blur (two-pass)<br>
Всё в одном файле, как ты просил.<br>
&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
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
from termin.visualization.components import MeshRenderer<br>
from termin.visualization.shader import ShaderProgram<br>
from termin.visualization.skybox import SkyBoxEntity<br>
from termin.visualization.posteffects.gray import GrayscaleEffect<br>
from termin.visualization.posteffects.blur import GaussianBlurPass<br>
<br>
# ================================================================<br>
#          СЦЕНА<br>
# ================================================================<br>
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
<br>
&#9;vec3 texColor = texture(u_diffuse_map, v_texcoord).rgb;<br>
&#9;float ndotl = max(dot(N, L), 0.0);<br>
<br>
&#9;vec3 diffuse = texColor * ndotl;<br>
&#9;vec3 ambient = texColor * 0.2;<br>
&#9;vec3 H = normalize(L + V);<br>
&#9;float spec = pow(max(dot(N, H), 0.0), 32.0);<br>
&#9;vec3 specular = vec3(0.4) * spec;<br>
<br>
&#9;vec3 color = (ambient + diffuse) * u_light_color + specular;<br>
&#9;FragColor = vec4(color, 1.0);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
def build_scene(world):<br>
&#9;texture_path = &quot;examples/data/textures/crate_diffuse.png&quot;<br>
&#9;texture = Texture.from_file(texture_path)<br>
<br>
&#9;mesh = TexturedCubeMesh()<br>
&#9;drawable = MeshDrawable(mesh)<br>
&#9;material = Material(<br>
&#9;&#9;shader=ShaderProgram(VERT, FRAG),<br>
&#9;&#9;color=None,<br>
&#9;&#9;textures={&quot;u_diffuse_map&quot;: texture},<br>
&#9;)<br>
<br>
&#9;cube = Entity(pose=Pose3.identity())<br>
&#9;cube.add_component(MeshRenderer(drawable, material))<br>
<br>
&#9;scene = Scene()<br>
&#9;scene.add(cube)<br>
&#9;scene.add(SkyBoxEntity())<br>
&#9;world.add_scene(scene)<br>
<br>
&#9;cam_ent = Entity()<br>
&#9;cam = PerspectiveCameraComponent()<br>
&#9;cam_ent.add_component(cam)<br>
&#9;cam_ent.add_component(OrbitCameraController())<br>
&#9;scene.add(cam_ent)<br>
<br>
&#9;return scene, cam<br>
<br>
<br>
# ================================================================<br>
#          MAIN<br>
# ================================================================<br>
<br>
def main():<br>
&#9;world = VisualizationWorld()<br>
<br>
&#9;scene, cam = build_scene(world)<br>
<br>
&#9;win = world.create_window(title=&quot;Cube + Grayscale + Gaussian Blur&quot;)<br>
&#9;vp = win.add_viewport(scene, cam)<br>
<br>
&#9;postprocess = vp.find_render_pass(&quot;PostFX&quot;)<br>
<br>
&#9;# цепочка: Grayscale → Blur Horizontal → Blur Vertical<br>
&#9;postprocess.add_effect(GrayscaleEffect())<br>
&#9;postprocess.add_effect(GaussianBlurPass(direction=(1.0, 0.0)))  # horizontal<br>
&#9;postprocess.add_effect(GaussianBlurPass(direction=(0.0, 1.0)))  # vertical<br>
<br>
&#9;world.run()<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
&#9;main()<br>
<!-- END SCAT CODE -->
</body>
</html>
