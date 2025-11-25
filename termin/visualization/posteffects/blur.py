import numpy as np
from ..shader import ShaderProgram

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