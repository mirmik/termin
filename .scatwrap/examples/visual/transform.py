<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/transform.py</title>
</head>
<body>
<pre><code>
&quot;&quot;&quot;Textured cube demo using the component-based visualization world.&quot;&quot;&quot;

from __future__ import annotations

import numpy as np

from termin.geombase.pose3 import Pose3
from termin.mesh.mesh import TexturedCubeMesh
from termin.visualization import (
    Entity,
    MeshDrawable,
    Scene,
    Material,
    Texture,
    VisualizationWorld,
    PerspectiveCameraComponent,
    OrbitCameraController,
)
from termin.visualization.components import MeshRenderer
from termin.visualization.shader import ShaderProgram
from termin.visualization.skybox import SkyBoxEntity


VERT = &quot;&quot;&quot;
#version 330 core
layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_texcoord;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_normal;
out vec3 v_world_pos;
out vec2 v_texcoord;

void main() {
    vec4 world = u_model * vec4(a_position, 1.0);
    v_world_pos = world.xyz;
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;
    v_texcoord = a_texcoord;
    gl_Position = u_projection * u_view * world;
}
&quot;&quot;&quot;


FRAG = &quot;&quot;&quot;
#version 330 core
in vec3 v_normal;
in vec3 v_world_pos;
in vec2 v_texcoord;

uniform vec3 u_light_dir;
uniform vec3 u_light_color;
uniform vec3 u_view_pos;
uniform sampler2D u_diffuse_map;

out vec4 FragColor;

void main() {
    vec3 N = normalize(v_normal);
    vec3 L = normalize(-u_light_dir);
    vec3 V = normalize(u_view_pos - v_world_pos);
    vec3 texColor = texture(u_diffuse_map, v_texcoord).rgb;
    float ndotl = max(dot(N, L), 0.0);
    vec3 diffuse = texColor * ndotl;
    vec3 ambient = texColor * 0.2;
    vec3 H = normalize(L + V);
    float spec = pow(max(dot(N, H), 0.0), 32.0);
    vec3 specular = vec3(0.4) * spec;
    vec3 color = (ambient + diffuse) * u_light_color + specular;
    FragColor = vec4(color, 1.0);
}
&quot;&quot;&quot;


def build_scene(world: VisualizationWorld) -&gt; tuple[Scene, PerspectiveCameraComponent]:
    texture_path = &quot;examples/data/textures/crate_diffuse.png&quot;
    texture = Texture.from_file(texture_path)
    mesh = TexturedCubeMesh()
    drawable = MeshDrawable(mesh)
    shader_prog = ShaderProgram(VERT, FRAG)
    material = Material(shader=shader_prog, color=None, textures={&quot;u_diffuse_map&quot;: texture})

    cube1 = Entity(pose=Pose3.identity(), name=&quot;cube&quot;)
    cube1.add_component(MeshRenderer(drawable, material))
    cube1.transform.relocate(Pose3(lin=np.array([-2.0, 0.0, 0.0])))

    cube2 = Entity(pose=Pose3.identity(), name=&quot;cube&quot;)
    cube2.add_component(MeshRenderer(drawable, material))
    cube2.transform.relocate(Pose3(lin= np.array([0.0, 0.0, 1.0])))
    cube2.transform.set_parent(cube1.transform)

    scene = Scene()
    scene.add(cube1)
    scene.add(cube2)
    scene.add(SkyBoxEntity())
    world.add_scene(scene)

    camera_entity = Entity(name=&quot;camera&quot;)
    camera = PerspectiveCameraComponent()
    camera_entity.add_component(camera)
    camera_entity.add_component(OrbitCameraController())
    scene.add(camera_entity)

    return scene, camera


def main():
    world = VisualizationWorld()
    scene, camera = build_scene(world)
    window = world.create_window(title=&quot;termin textured cube&quot;)
    window.add_viewport(scene, camera)
    world.run()


if __name__ == &quot;__main__&quot;:
    main()

</code></pre>
</body>
</html>
