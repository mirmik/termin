import numpy as np
from tgfx import TcShader
from ..postprocess import PostEffect
from termin.editor.inspect_field import InspectField

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

# Lazy-loaded shared shader
_blur_shader: TcShader | None = None

def _get_blur_shader() -> TcShader:
    global _blur_shader
    if _blur_shader is None:
        _blur_shader = TcShader.from_sources(GAUSS_VERT, GAUSS_FRAG, "", "GaussianBlur")
    return _blur_shader


class GaussianBlurPass(PostEffect):
    """Один проход: горизонтальный или вертикальный."""

    name = "gaussian_blur"

    inspect_fields = {
        "direction": InspectField(
            path="direction",
            label="Direction",
            kind="enum",
            choices=[
                ((1.0, 0.0), "Horizontal"),
                ((0.0, 1.0), "Vertical"),
            ],
        ),
    }

    def __init__(self, direction=(1.0, 0.0)):
        self.direction = np.array(direction, dtype=np.float32)

    def draw(self, ctx2, color_tex2, target_tex2, extra_tex2, size):
        from tgfx._tgfx_native import tc_shader_ensure_tgfx2

        w, h = size
        texel_size = (1.0 / max(1, w), 1.0 / max(1, h))

        shader = _get_blur_shader()
        pair = tc_shader_ensure_tgfx2(ctx2, shader)
        if not pair.vs or not pair.fs:
            return

        def setup(ctx2):
            ctx2.bind_shader(pair.vs, pair.fs)
            ctx2.bind_sampled_texture(0, color_tex2)
            ctx2.set_uniform_int("u_texture", 0)
            ctx2.set_uniform_vec2("u_texel_size", texel_size[0], texel_size[1])
            ctx2.set_uniform_vec2("u_direction", float(self.direction[0]), float(self.direction[1]))
            ctx2.draw_fullscreen_quad()

        PostEffect._simple_draw(ctx2, target_tex2, size, setup)