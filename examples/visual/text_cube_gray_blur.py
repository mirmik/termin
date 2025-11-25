"""
Textured cube demo + grayscale + Gaussian blur (two-pass)
Всё в одном файле, как ты просил.
"""

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

# ================================================================
#                   GRAYSCALE EFFECT
# ================================================================

GRAY_VERT = """
#version 330 core
layout(location=0) in vec2 a_pos;
layout(location=1) in vec2 a_uv;
out vec2 v_uv;
void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""

GRAY_FRAG = """
#version 330 core
in vec2 v_uv;
uniform sampler2D u_texture;
out vec4 FragColor;

void main() {
    vec3 c = texture(u_texture, v_uv).rgb;
    float g = dot(c, vec3(0.299, 0.587, 0.114));
    FragColor = vec4(g, g, g, 1.0);
}
"""

class GrayscalePostProcess:
    def __init__(self):
        self.shader = ShaderProgram(GRAY_VERT, GRAY_FRAG)

    def draw(self, graphics, ctx, tex, viewport_size):
        self.shader.ensure_ready(graphics)
        self.shader.use()
        tex.bind(0)
        self.shader.set_uniform_int("u_texture", 0)

        graphics.set_depth_test(False)
        graphics.set_cull_face(False)
        graphics.set_blend(False)

        graphics.draw_ui_textured_quad(ctx)


# ================================================================
#          TWO-PASS GAUSSIAN BLUR (H + V)
# ================================================================

GAUSS_VERT = GRAY_VERT  # полностью годится

GAUSS_FRAG = """
#version 330 core
in vec2 v_uv;

uniform sampler2D u_texture;
uniform vec2 u_direction;   // (1,0) for horizontal, (0,1) for vertical
uniform vec2 u_texel_size;  // 1.0 / resolution

out vec4 FragColor;

// 5-tap gaussian weights (approx sigma=2)
const float w0 = 0.227027;
const float w1 = 0.316216;
const float w2 = 0.070270;

void main() {
    vec2 ts = u_texel_size;
    vec2 dir = u_direction;

    vec3 c = texture(u_texture, v_uv).rgb * w0;
    c += texture(u_texture, v_uv + dir * ts * 1.0).rgb * w1;
    c += texture(u_texture, v_uv - dir * ts * 1.0).rgb * w1;
    c += texture(u_texture, v_uv + dir * ts * 2.0).rgb * w2;
    c += texture(u_texture, v_uv - dir * ts * 2.0).rgb * w2;

    FragColor = vec4(c, 1.0);
}
"""

class GaussianBlurPass:
    """Один проход: горизонтальный или вертикальный."""

    def __init__(self, direction):
        self.shader = ShaderProgram(GAUSS_VERT, GAUSS_FRAG)
        self.direction = np.array(direction, dtype=np.float32)

    def draw(self, graphics, ctx, tex, viewport_size):
        w, h = viewport_size
        texel_size = np.array([1.0/max(1,w), 1.0/max(1,h)], dtype=np.float32)

        self.shader.ensure_ready(graphics)
        self.shader.use()

        tex.bind(0)
        self.shader.set_uniform_int("u_texture", 0)
        self.shader.set_uniform_auto("u_texel_size", texel_size)
        self.shader.set_uniform_auto("u_direction", self.direction)

        graphics.set_depth_test(False)
        graphics.set_cull_face(False)
        graphics.set_blend(False)

        graphics.draw_ui_textured_quad(ctx)


class GaussianBlurPostProcess:
    """Двухпроходный blur (H + V)."""

    def __init__(self):
        self.pass_h = GaussianBlurPass((1.0, 0.0))
        self.pass_v = GaussianBlurPass((0.0, 1.0))

    def draw(self, graphics, ctx, tex, viewport_size):
        # тут вызывается РОВНО ОДИН проход;
        # второй будет выполняться в цепочке постпроцессов
        self.shader = None  # не используется
        raise RuntimeError("Этот класс – контейнер двух стадий, он не вызывается напрямую.")


# ================================================================
#          СЦЕНА
# ================================================================

VERT = """
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
"""

FRAG = """
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
"""


def build_scene(world):
    texture_path = "examples/data/textures/crate_diffuse.png"
    texture = Texture.from_file(texture_path)

    mesh = TexturedCubeMesh()
    drawable = MeshDrawable(mesh)
    material = Material(
        shader=ShaderProgram(VERT, FRAG),
        color=None,
        textures={"u_diffuse_map": texture},
    )

    cube = Entity(pose=Pose3.identity())
    cube.add_component(MeshRenderer(drawable, material))

    scene = Scene()
    scene.add(cube)
    scene.add(SkyBoxEntity())
    world.add_scene(scene)

    cam_ent = Entity()
    cam = PerspectiveCameraComponent()
    cam_ent.add_component(cam)
    cam_ent.add_component(OrbitCameraController())
    scene.add(cam_ent)

    return scene, cam


# ================================================================
#          MAIN
# ================================================================

def main():
    world = VisualizationWorld()

    scene, cam = build_scene(world)

    win = world.create_window(title="Cube + Grayscale + Gaussian Blur")
    vp = win.add_viewport(scene, cam)

    blur = GaussianBlurPostProcess()

    # цепочка: Grayscale → Blur Horizontal → Blur Vertical
    vp.add_postprocess(GrayscalePostProcess())
    vp.add_postprocess(blur.pass_h)
    vp.add_postprocess(blur.pass_v)

    world.run()


if __name__ == "__main__":
    main()
