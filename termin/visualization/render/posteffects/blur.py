import numpy as np
from ..shader import ShaderProgram
from ..postprocess import PostEffect

# ================================================================
#          TWO-PASS GAUSSIAN BLUR (H + V)
# ================================================================

GAUSS_VERT = """
#version 330 core
layout(location=0) in vec2 a_pos;
layout(location=1) in vec2 a_uv;
out vec2 v_uv;
void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""

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

class GaussianBlurPass(PostEffect):
    """Один проход: горизонтальный или вертикальный."""

    name = "gaussian_blur"

    def __init__(self, direction=(1.0, 0.0)):
        self.shader = ShaderProgram(GAUSS_VERT, GAUSS_FRAG)
        self.direction = np.array(direction, dtype=np.float32)

    def _serialize_params(self) -> dict:
        """Сериализует параметры GaussianBlurPass."""
        return {
            "direction": self.direction.tolist(),
        }

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "GaussianBlurPass":
        """Создаёт GaussianBlurPass из сериализованных данных."""
        direction = tuple(data.get("direction", (1.0, 0.0)))
        return cls(direction=direction)

    def draw(self, gfx, key, color_tex, extra_textures, size):
        w, h = size
        texel_size = np.array([1.0/max(1,w), 1.0/max(1,h)], dtype=np.float32)

        self.shader.ensure_ready(gfx)
        self.shader.use()

        color_tex.bind(0)
        self.shader.set_uniform_int("u_texture", 0)
        self.shader.set_uniform_auto("u_texel_size", texel_size)
        self.shader.set_uniform_auto("u_direction", self.direction)

        gfx.set_depth_test(False)
        gfx.set_cull_face(False)
        gfx.set_blend(False)

        gfx.draw_ui_textured_quad(key)