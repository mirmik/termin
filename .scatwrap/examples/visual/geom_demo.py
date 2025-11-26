<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/geom_demo.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;<br>
Demo: rendering cube wireframe using a geometry shader.<br>
&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
import numpy as np<br>
<br>
from termin.geombase.pose3 import Pose3<br>
from termin.mesh.mesh import CubeMesh<br>
from termin.visualization import (<br>
    Entity,<br>
    MeshDrawable,<br>
    Scene,<br>
    Material,<br>
    VisualizationWorld,<br>
    PerspectiveCameraComponent,<br>
    OrbitCameraController,<br>
)<br>
from termin.visualization.components import MeshRenderer<br>
from termin.visualization.shader import ShaderProgram<br>
from termin.visualization.skybox import SkyBoxEntity<br>
<br>
<br>
# =============================<br>
#   Vertex Shader<br>
# =============================<br>
vert = &quot;&quot;&quot;<br>
#version 330 core<br>
<br>
layout(location = 0) in vec3 a_position;<br>
<br>
uniform mat4 u_model;<br>
uniform mat4 u_view;<br>
uniform mat4 u_projection;<br>
<br>
out vec3 v_pos_world;<br>
<br>
void main() {<br>
    vec4 world = u_model * vec4(a_position, 1.0);<br>
    v_pos_world = world.xyz;<br>
<br>
    gl_Position = u_projection * u_view * world;<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
# =============================<br>
#   Geometry Shader (line generation)<br>
# =============================<br>
geom = &quot;&quot;&quot;<br>
#version 330 core<br>
<br>
layout(triangles) in;<br>
layout(line_strip, max_vertices = 6) out;<br>
<br>
in vec3 v_pos_world[];<br>
<br>
out vec3 g_pos_world;<br>
<br>
void main() {<br>
    // три вершины входного треугольника<br>
    for (int i = 0; i &lt; 3; i++) {<br>
        int j = (i + 1) % 3;<br>
<br>
        g_pos_world = v_pos_world[i];<br>
        gl_Position = gl_in[i].gl_Position;<br>
        EmitVertex();<br>
<br>
        g_pos_world = v_pos_world[j];<br>
        gl_Position = gl_in[j].gl_Position;<br>
        EmitVertex();<br>
<br>
        EndPrimitive();<br>
    }<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
# =============================<br>
#   Fragment Shader<br>
# =============================<br>
frag = &quot;&quot;&quot;<br>
#version 330 core<br>
<br>
in vec3 g_pos_world;<br>
<br>
uniform vec4 u_color;<br>
<br>
out vec4 FragColor;<br>
<br>
void main() {<br>
    // просто цвет линий<br>
    FragColor = vec4(u_color.rgb, u_color.a);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
# =============================<br>
#   Scene builder<br>
# =============================<br>
def build_scene(world: VisualizationWorld):<br>
    cube_mesh = CubeMesh()<br>
    drawable = MeshDrawable(cube_mesh)<br>
<br>
    # теперь прокидываем третий аргумент — geometry shader<br>
    shader_prog = ShaderProgram(<br>
        vertex_source=vert,<br>
        fragment_source=frag,<br>
        geometry_source=geom,<br>
    )<br>
<br>
    # красим линии (красный wireframe)<br>
    material = Material(<br>
        shader=shader_prog,<br>
        color=np.array([1.0, 0.1, 0.1, 1.0], dtype=np.float32)<br>
    )<br>
<br>
    entity = Entity(pose=Pose3.identity(), name=&quot;wire_cube&quot;)<br>
    entity.add_component(MeshRenderer(drawable, material))<br>
<br>
    scene = Scene()<br>
    scene.add(entity)<br>
<br>
    # оставляем небо для красоты<br>
    skybox = SkyBoxEntity()<br>
    scene.add(skybox)<br>
<br>
    world.add_scene(scene)<br>
<br>
    # камера как в базовом примере<br>
    camera_entity = Entity(name=&quot;camera&quot;)<br>
    camera = PerspectiveCameraComponent()<br>
    camera_entity.add_component(camera)<br>
    camera_entity.add_component(OrbitCameraController())<br>
    scene.add(camera_entity)<br>
<br>
    return scene, camera<br>
<br>
<br>
# =============================<br>
#   Main<br>
# =============================<br>
def main():<br>
    world = VisualizationWorld()<br>
    scene, camera = build_scene(world)<br>
    window = world.create_window(title=&quot;termin geometry-shader wireframe demo&quot;)<br>
    window.add_viewport(scene, camera)<br>
    world.run()<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
    main()<br>
<!-- END SCAT CODE -->
</body>
</html>
