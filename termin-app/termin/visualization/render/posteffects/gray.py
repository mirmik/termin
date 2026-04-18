from termin.visualization.render.postprocess import PostEffect
from tgfx._tgfx_native import Tgfx2ShaderStage


# Backend-neutral FSQ vertex + fragment pair. `#version 450 core` with
# explicit `layout(location=N)` on every interface variable — mandatory
# for Vulkan shaderc (SPIR-V requires locations), and accepted on GL 4.3+
# via core GL_ARB_shading_language_420pack. The sampler sits at binding 4
# to match tgfx2's shared descriptor layout (UBO 0-3, sampler 4-7).
GRAY_VERT = """#version 450 core
layout(location=0) in vec2 a_pos;
layout(location=1) in vec2 a_uv;
layout(location=0) out vec2 v_uv;

void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""

GRAY_FRAG = """#version 450 core
layout(location=0) in vec2 v_uv;
layout(binding=4) uniform sampler2D u_texture;
layout(location=0) out vec4 FragColor;

void main() {
    vec3 c = texture(u_texture, v_uv).rgb;
    float g = dot(c, vec3(0.299, 0.587, 0.114));
    FragColor = vec4(g, g, g, 1.0);
}
"""


class GrayscaleEffect(PostEffect):
    name = "grayscale"

    def __init__(self):
        self._vs = None
        self._fs = None

    def required_resources(self) -> set[str]:
        return set()

    def _ensure_shaders(self, ctx2):
        if self._vs is None:
            self._vs = ctx2.device.create_shader(Tgfx2ShaderStage.Vertex, GRAY_VERT)
        if self._fs is None:
            self._fs = ctx2.device.create_shader(Tgfx2ShaderStage.Fragment, GRAY_FRAG)

    def draw(self, ctx2, color_tex2, target_tex2, extra_tex2, size):
        self._ensure_shaders(ctx2)
        if not self._vs or not self._fs:
            return

        def setup(ctx2):
            ctx2.bind_shader(self._vs, self._fs)
            ctx2.bind_sampled_texture(4, color_tex2)
            ctx2.draw_fullscreen_quad()

        PostEffect._simple_draw(ctx2, target_tex2, size, setup)
