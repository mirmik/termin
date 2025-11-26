<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/geom_demo.py</title>
</head>
<body>
<pre><code>
&quot;&quot;&quot;
Demo: rendering cube wireframe using a geometry shader.
&quot;&quot;&quot;

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
)
from termin.visualization.components import MeshRenderer
from termin.visualization.shader import ShaderProgram
from termin.visualization.skybox import SkyBoxEntity


# =============================
#   Vertex Shader
# =============================
vert = &quot;&quot;&quot;
#version 330 core

layout(location = 0) in vec3 a_position;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_pos_world;

void main() {
    vec4 world = u_model * vec4(a_position, 1.0);
    v_pos_world = world.xyz;

    gl_Position = u_projection * u_view * world;
}
&quot;&quot;&quot;


# =============================
#   Geometry Shader (line generation)
# =============================
geom = &quot;&quot;&quot;
#version 330 core

layout(triangles) in;
layout(line_strip, max_vertices = 6) out;

in vec3 v_pos_world[];

out vec3 g_pos_world;

void main() {
    // три вершины входного треугольника
    for (int i = 0; i &lt; 3; i++) {
        int j = (i + 1) % 3;

        g_pos_world = v_pos_world[i];
        gl_Position = gl_in[i].gl_Position;
        EmitVertex();

        g_pos_world = v_pos_world[j];
        gl_Position = gl_in[j].gl_Position;
        EmitVertex();

        EndPrimitive();
    }
}
&quot;&quot;&quot;


# =============================
#   Fragment Shader
# =============================
frag = &quot;&quot;&quot;
#version 330 core

in vec3 g_pos_world;

uniform vec4 u_color;

out vec4 FragColor;

void main() {
    // просто цвет линий
    FragColor = vec4(u_color.rgb, u_color.a);
}
&quot;&quot;&quot;


# =============================
#   Scene builder
# =============================
def build_scene(world: VisualizationWorld):
    cube_mesh = CubeMesh()
    drawable = MeshDrawable(cube_mesh)

    # теперь прокидываем третий аргумент — geometry shader
    shader_prog = ShaderProgram(
        vertex_source=vert,
        fragment_source=frag,
        geometry_source=geom,
    )

    # красим линии (красный wireframe)
    material = Material(
        shader=shader_prog,
        color=np.array([1.0, 0.1, 0.1, 1.0], dtype=np.float32)
    )

    entity = Entity(pose=Pose3.identity(), name=&quot;wire_cube&quot;)
    entity.add_component(MeshRenderer(drawable, material))

    scene = Scene()
    scene.add(entity)

    # оставляем небо для красоты
    skybox = SkyBoxEntity()
    scene.add(skybox)

    world.add_scene(scene)

    # камера как в базовом примере
    camera_entity = Entity(name=&quot;camera&quot;)
    camera = PerspectiveCameraComponent()
    camera_entity.add_component(camera)
    camera_entity.add_component(OrbitCameraController())
    scene.add(camera_entity)

    return scene, camera


# =============================
#   Main
# =============================
def main():
    world = VisualizationWorld()
    scene, camera = build_scene(world)
    window = world.create_window(title=&quot;termin geometry-shader wireframe demo&quot;)
    window.add_viewport(scene, camera)
    world.run()


if __name__ == &quot;__main__&quot;:
    main()

</code></pre>
</body>
</html>
