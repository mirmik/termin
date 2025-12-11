"""
demo_wire_cube.py

Куб, рисуемый в два прохода:
1) обычный solid-шейдер
2) поверх него — wireframe через геометрический шейдер

Толщина линий передаётся в шейдер как uniform u_line_width.
(Чтобы она реально влияла на визуал, нужно дописать более хитрый GS;
сейчас это просто пример того, как параметр уходит в материал/шейдер.)
"""

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
from termin.visualization.render.components import MeshRenderer, LightComponent
from termin.visualization.render.shader import ShaderProgram

from termin.visualization.render.renderpass import RenderPass, RenderState


# ----------------------------------------------------------------------
# SOLID SHADER (почти твой исходный)
# ----------------------------------------------------------------------

SOLID_VERT = """
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
"""

SOLID_FRAG = """
#version 330 core

in vec3 v_normal;
in vec3 v_world_pos;

uniform vec4 u_color;
uniform vec3 u_light_dir;
uniform vec3 u_light_color;
uniform vec3 u_view_pos;

out vec4 FragColor;

void main() {
    vec3 N = normalize(v_normal);
    vec3 L = normalize(-u_light_dir);
    vec3 V = normalize(u_view_pos - v_world_pos);
    vec3 H = normalize(L + V);

    const float ambientStrength  = 0.2;
    const float diffuseStrength  = 0.8;
    const float specularStrength = 0.4;
    const float shininess        = 32.0;

    vec3 ambient = ambientStrength * u_color.rgb;

    float ndotl = max(dot(N, L), 0.0);
    vec3 diffuse = diffuseStrength * ndotl * u_color.rgb;

    float specFactor = 0.0;
    if (ndotl > 0.0) {
        specFactor = pow(max(dot(N, H), 0.0), shininess);
    }
    vec3 specular = specularStrength * specFactor * u_light_color;

    vec3 color = (ambient + diffuse) * u_light_color + specular;
    color = clamp(color, 0.0, 1.0);

    FragColor = vec4(color, u_color.a);
}
"""


# ----------------------------------------------------------------------
# WIREFRAME SHADERS
# ----------------------------------------------------------------------

# Вершинник — просто выдаём позицию в clip-space.
WIRE_VERT = """
#version 330 core
layout(location = 0) in vec3 a_position;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

void main() {
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""

# Геометрический шейдер: разворачивает треугольники в 3 линии.
# u_line_width сейчас просто существует как uniform (пример передачи параметра).
# Для реальной "толстой" линии нужен более сложный экранно-пространственный алгоритм.
WIRE_GEOM = """
#version 330 core

layout(triangles) in;
layout(triangle_strip, max_vertices = 12) out;

// Толщина в NDC (0..1 примерно как половина экрана).
uniform float u_line_width;
uniform mat4 u_projection; // если понадобится что-то хитрее, можно использовать

// Генерация "толстой" полоски вокруг отрезка p0-p1 в экранном пространстве
void emit_thick_segment(vec4 p0, vec4 p1)
{
    // Вершины в NDC
    vec2 ndc0 = p0.xy / p0.w;
    vec2 ndc1 = p1.xy / p1.w;

    vec2 dir = ndc1 - ndc0;
    float len2 = dot(dir, dir);
    if (len2 <= 1e-8)
        return;

    dir = normalize(dir);
    vec2 n = vec2(-dir.y, dir.x);      // перпендикуляр
    vec2 off = n * (u_line_width * 0.5);

    vec2 ndc0a = ndc0 + off;
    vec2 ndc0b = ndc0 - off;
    vec2 ndc1a = ndc1 + off;
    vec2 ndc1b = ndc1 - off;

    // Обратно в clip-space
    vec4 p0a = vec4(ndc0a * p0.w, p0.zw);
    vec4 p0b = vec4(ndc0b * p0.w, p0.zw);
    vec4 p1a = vec4(ndc1a * p1.w, p1.zw);
    vec4 p1b = vec4(ndc1b * p1.w, p1.zw);

    // Квад из двух треугольников (triangle_strip)
    gl_Position = p0a; EmitVertex();
    gl_Position = p0b; EmitVertex();
    gl_Position = p1a; EmitVertex();
    gl_Position = p1b; EmitVertex();
    EndPrimitive();
}

void main()
{
    vec4 p0 = gl_in[0].gl_Position;
    vec4 p1 = gl_in[1].gl_Position;
    vec4 p2 = gl_in[2].gl_Position;

    // три рёбра треугольника
    emit_thick_segment(p0, p1);
    emit_thick_segment(p1, p2);
    emit_thick_segment(p2, p0);
}

"""

WIRE_FRAG = """
#version 330 core

uniform vec4 u_color;

out vec4 FragColor;

void main() {
    FragColor = u_color;
}
"""


# ----------------------------------------------------------------------
# SCENE BUILDING
# ----------------------------------------------------------------------

def build_scene(world: VisualizationWorld):
    # Меш куба
    cube_mesh = CubeMesh()
    drawable = MeshDrawable(cube_mesh)

    # --- Solid материал ---
    solid_shader = ShaderProgram(SOLID_VERT, SOLID_FRAG)
    solid_material = Material(
        shader=solid_shader,
        color=np.array([0.8, 0.3, 0.3, 1.0], dtype=np.float32),
    )

    solid_pass = RenderPass.from_material(
        solid_material,
        state=RenderState(
            polygon_mode="fill",
            cull=True,
            depth_test=True,
            depth_write=True,
            blend=False,
        ),
    )

    # --- Wireframe материал ---
    wire_shader = ShaderProgram(
        vertex_source=WIRE_VERT,
        fragment_source=WIRE_FRAG,
        geometry_source=WIRE_GEOM,
    )

    wire_material = Material(
        shader=wire_shader,
        color=np.array([0.05, 0.05, 0.05, 1.0], dtype=np.float32),
        uniforms={
            # вот сюда можно подсунуть толщину, шейдер её получит:
            "u_line_width": 0.01,
        },
    )

    wire_pass = RenderPass.from_material(
        wire_material,
        state=RenderState(
            polygon_mode="fill",   # <-- ВАЖНО: теперь fill, не line
            cull=False,
            depth_test=True,
            depth_write=False,
            blend=False,
        ),
    )

    # --- Entity с MeshRenderer, использующим два прохода ---
    entity = Entity(pose=Pose3.identity(), name="wire_cube")
    entity.add_component(
        MeshRenderer(
            mesh=drawable,
            material=solid_material,          # основной материал (для обратной совместимости)
            passes=[solid_pass, wire_pass],   # мультипасс
        )
    )

    # --- Scene + камера ---
    scene = Scene()
    scene.add(entity)

    world.add_scene(scene)

    # Light
    light_entity = Entity(
        pose=Pose3.from_euler(np.deg2rad(-45), np.deg2rad(-45), 0),
        name="light",
    )
    light_entity.add_component(LightComponent())
    scene.add(light_entity)

    # Camera
    camera_entity = Entity(name="camera")
    camera = PerspectiveCameraComponent()
    camera_entity.add_component(camera)
    camera_entity.add_component(OrbitCameraController())
    scene.add(camera_entity)

    return scene, camera


def main():
    world = VisualizationWorld()
    scene, camera = build_scene(world)

    window = world.create_window(title="termin wireframe demo")
    window.add_viewport(scene, camera)

    world.run()


if __name__ == "__main__":
    main()
