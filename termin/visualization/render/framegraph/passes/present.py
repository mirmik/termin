from __future__ import annotations

from termin.visualization.render.framegraph.context import FrameContext
from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.visualization.render.shader import ShaderProgram


def blit_fbo_to_fbo(
    gfx: "GraphicsBackend",
    src_fb,
    dst_fb,
    size: tuple[int, int],
    context_key: int,
):
    w, h = size

    # целевой FBO
    gfx.bind_framebuffer(dst_fb)
    gfx.set_viewport(0, 0, w, h)

    # глубина нам не нужна
    gfx.set_depth_test(False)
    gfx.set_depth_mask(False)

    # берём ту же фуллскрин-квад-программу, что и PresentToScreenPass
    shader = PresentToScreenPass._get_shader()
    shader.ensure_ready(gfx)
    shader.use()
    shader.set_uniform_int("u_tex", 0)

    tex = src_fb.color_texture()
    tex.bind(0)

    gfx.draw_ui_textured_quad(context_key)

    gfx.set_depth_test(True)
    gfx.set_depth_mask(True)


FSQ_VERT = """
#version 330 core
layout(location = 0) in vec2 a_pos;
layout(location = 1) in vec2 a_uv;

out vec2 v_uv;

void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""

FSQ_FRAG = """
#version 330 core
in vec2 v_uv;
out vec4 FragColor;

uniform sampler2D u_tex;

void main() {
    FragColor = texture(u_tex, v_uv);
}
"""


class PresentToScreenPass(RenderFramePass):
    """
    Берёт текстуру из ресурса input_res и выводит её на экран
    фуллскрин-квадом.
    """

    _shader: ShaderProgram | None = None

    def __init__(self, input_res: str, pass_name: str = "PresentToScreen"):
        super().__init__(
            pass_name=pass_name,
            reads={input_res},
            writes=set(),  # экран считаем внешним
            inplace=False,
        )
        self.input_res = input_res

    @classmethod
    def _get_shader(cls) -> ShaderProgram:
        if cls._shader is None:
            cls._shader = ShaderProgram(FSQ_VERT, FSQ_FRAG)
        return cls._shader

    def execute(self, ctx: FrameContext):
        gfx = ctx.graphics
        window = ctx.window
        px, py, pw, ph = ctx.rect
        key = ctx.context_key

        fb_in = ctx.fbos.get(self.input_res)
        if fb_in is None:
            return

        tex_in = fb_in.color_texture()

        window.handle.bind_window_framebuffer()
        gfx.set_viewport(px, py, pw, ph)

        gfx.set_depth_test(False)
        gfx.set_depth_mask(False)

        shader = self._get_shader()
        shader.ensure_ready(gfx)
        shader.use()
        shader.set_uniform_int("u_tex", 0)

        tex_in.bind(0)

        gfx.draw_ui_textured_quad(key)

        gfx.set_depth_test(True)
        gfx.set_depth_mask(True)
