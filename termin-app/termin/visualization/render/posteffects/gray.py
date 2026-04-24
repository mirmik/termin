from tgfx import TcShader
from termin.visualization.render.postprocess import PostEffect


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

class GrayscaleEffect(PostEffect):
    name = "grayscale"

    def __init__(self):
        self._shader: TcShader | None = None

    def required_resources(self) -> set[str]:
        return set()

    def _get_shader(self) -> TcShader:
        if self._shader is None:
            self._shader = TcShader.from_sources(GRAY_VERT, GRAY_FRAG, "", "GrayscaleEffect")
        return self._shader

    def draw(self, ctx2, color_tex2, target_tex2, extra_tex2, size):
        from tgfx._tgfx_native import tc_shader_ensure_tgfx2
        shader = self._get_shader()
        pair = tc_shader_ensure_tgfx2(ctx2, shader)
        if not pair.vs or not pair.fs:
            return

        def setup(ctx2):
            ctx2.bind_shader(pair.vs, pair.fs)
            ctx2.bind_sampled_texture(0, color_tex2)
            ctx2.set_uniform_int("u_texture", 0)
            ctx2.draw_fullscreen_quad()

        PostEffect._simple_draw(ctx2, target_tex2, size, setup)
