<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/keyframe_animation.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Keyframed animation demo: translation + rotation + scale.&quot;&quot;&quot;<br>
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
from termin.visualization.animation import (<br>
    AnimationChannel,<br>
    AnimationClip,<br>
    AnimationPlayer,<br>
    AnimationKeyframe,<br>
)<br>
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
<br>
uniform vec4 u_color;<br>
uniform vec3 u_light_dir;<br>
<br>
out vec4 FragColor;<br>
<br>
void main() {<br>
    vec3 N = normalize(v_normal);<br>
    float ndotl = max(dot(N, -normalize(u_light_dir)), 0.0);<br>
    vec3 color = u_color.rgb * (0.2 + 0.8 * ndotl);<br>
    FragColor = vec4(color, u_color.a);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
<br>
def build_scene(world: VisualizationWorld):<br>
    mesh = MeshDrawable(CubeMesh(size=1.0))<br>
    shader = ShaderProgram(VERT, FRAG)<br>
    material = Material(<br>
        shader=shader,<br>
        color=np.array([0.4, 0.9, 0.4, 1.0], dtype=np.float32),<br>
    )<br>
<br>
    cube = Entity(pose=Pose3.identity(), name=&quot;animated_cube&quot;)<br>
    cube.add_component(MeshRenderer(mesh, material))<br>
<br>
    # ============<br>
    # Keyframes<br>
    # ============<br>
<br>
    # движение по &quot;квадрату&quot;<br>
    trs_keys = [<br>
        AnimationKeyframe(0.0, translation=np.array([1.5, 0.0, 0.0])),<br>
        AnimationKeyframe(1.0, translation=np.array([0.0, 1.5, 0.0])),<br>
        AnimationKeyframe(2.0, translation=np.array([-1.5, 0.0, 0.0])),<br>
        AnimationKeyframe(3.0, translation=np.array([0.0, -1.5, 0.0])),<br>
        AnimationKeyframe(4.0, translation=np.array([1.5, 0.0, 0.0])),<br>
    ]<br>
<br>
    # полный оборот вокруг Y за 4 секунды<br>
    rot_keys = [<br>
        AnimationKeyframe(0.0, rotation=Pose3.rotateY(0.0).ang),<br>
        AnimationKeyframe(1.0, rotation=Pose3.rotateY(np.pi/2).ang),<br>
        AnimationKeyframe(2.0, rotation=Pose3.rotateY(np.pi).ang),<br>
        AnimationKeyframe(3.0, rotation=Pose3.rotateY(1.5 * np.pi).ang),<br>
        AnimationKeyframe(4.0, rotation=Pose3.rotateY(2.0 * np.pi).ang),<br>
    ]<br>
<br>
    # пульсация масштаба<br>
    scale_keys = [<br>
        AnimationKeyframe(0.0, scale=1.0),<br>
        AnimationKeyframe(1.0, scale=1.5),<br>
        AnimationKeyframe(2.0, scale=1.0),<br>
        AnimationKeyframe(3.0, scale=0.7),<br>
        AnimationKeyframe(4.0, scale=1.0),<br>
    ]<br>
<br>
    clip = AnimationClip(<br>
        &quot;move_rotate_scale&quot;,<br>
        tps = 1.0,  # тики в секунду<br>
        channels={<br>
            &quot;clip&quot; :AnimationChannel(translation_keys=trs_keys, rotation_keys=rot_keys, scale_keys=scale_keys)<br>
        },<br>
        loop=True,<br>
    )<br>
<br>
    player = cube.add_component(AnimationPlayer())<br>
    player.add_clip(clip)<br>
    player.play(&quot;move_rotate_scale&quot;)<br>
<br>
    scene = Scene()<br>
    scene.add(cube)<br>
    scene.add(SkyBoxEntity())<br>
    world.add_scene(scene)<br>
<br>
    cam_entity = Entity(name=&quot;camera&quot;)<br>
    cam = PerspectiveCameraComponent()<br>
    cam_entity.add_component(cam)<br>
    cam_entity.add_component(OrbitCameraController(radius=6.0, elevation=30.0))<br>
    scene.add(cam_entity)<br>
<br>
    return scene, cam<br>
<br>
<br>
def main():<br>
    world = VisualizationWorld()<br>
    scene, cam = build_scene(world)<br>
    window = world.create_window(title=&quot;termin keyframed cube&quot;)<br>
    window.add_viewport(scene, cam)<br>
    world.run()<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
    main()<br>
<!-- END SCAT CODE -->
</body>
</html>
