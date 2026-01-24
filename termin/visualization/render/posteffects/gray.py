from termin._native.render import TcShader
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

    def draw(self, gfx, color_tex, extra_textures, size, target_fbo=None):
        shader = self._get_shader()
        shader.ensure_ready()
        shader.use()

        color_tex.bind(0)
        shader.set_uniform_int("u_texture", 0)

        gfx.draw_ui_textured_quad()
