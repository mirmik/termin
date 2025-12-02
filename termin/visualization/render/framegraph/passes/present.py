from __future__ import annotations

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


class BlitPass(RenderFramePass):
    """
    Копирует color-текстуру из одного FBO в другой через фуллскрин-квад.
    Источник задаётся колбэком get_source_res, чтобы его можно было
    динамически переключать из редактора/дебагера.

    Для отключения пасса используйте enabled=False.
    """

    def __init__(
        self,
        get_source_res,
        output_res: str = "debug",
        pass_name: str = "Blit",
    ):
        super().__init__(
            pass_name=pass_name,
            reads=set(),  # фактическое имя ресурса задаётся динамически
            writes={output_res},
            inplace=False,
        )
        self._get_source_res = get_source_res
        self.output_res = output_res
        self._current_src_name: str | None = None

    def required_resources(self) -> set[str]:
        resources = set(self.writes)
        if self._get_source_res is None:
            self._current_src_name = None
            self.reads = set()
            return resources

        src_name = self._get_source_res()
        if src_name:
            self._current_src_name = src_name
            self.reads = {src_name}
            resources.add(src_name)
        else:
            self.reads = set()
            self._current_src_name = None

        return resources

    def execute(
        self,
        graphics: "GraphicsBackend",
        reads_fbos: dict[str, "FramebufferHandle" | None],
        writes_fbos: dict[str, "FramebufferHandle" | None],
        rect: tuple[int, int, int, int],
        scene=None,
        camera=None,
        renderer=None,
        context_key: int,
        lights=None,
        canvas=None,
    ):
        px, py, pw, ph = rect
        key = context_key

        if self._get_source_res is None:
            return

        src_name = self._get_source_res()
        if not src_name:
            return

        fb_in = reads_fbos.get(src_name)
        if fb_in is None:
            return

        fb_out = writes_fbos.get(self.output_res)
        if fb_out is None:
            return
        
        blit_fbo_to_fbo(graphics, fb_in, fb_out, (pw, ph), key)
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
            writes={"DISPLAY"},
            inplace=False,
        )
        self.input_res = input_res

    @classmethod
    def _get_shader(cls) -> ShaderProgram:
        if cls._shader is None:
            cls._shader = ShaderProgram(FSQ_VERT, FSQ_FRAG)
        return cls._shader

    def execute(
        self,
        graphics: "GraphicsBackend",
        reads_fbos: dict[str, "FramebufferHandle" | None],
        writes_fbos: dict[str, "FramebufferHandle" | None],
        rect: tuple[int, int, int, int],
        scene=None,
        camera=None,
        renderer=None,
        context_key: int,
        lights=None,
        canvas=None,
    ):
        px, py, pw, ph = rect
        key = context_key

        fb_in = reads_fbos.get(self.input_res)
        fb_out = writes_fbos.get("DISPLAY")
        if fb_in is None or fb_out is None:
            return

        tex_in = fb_in.color_texture()

        graphics.bind_framebuffer(fb_out)
        graphics.set_viewport(px, py, pw, ph)

        graphics.set_depth_test(False)
        graphics.set_depth_mask(False)

        shader = self._get_shader()
        shader.ensure_ready(graphics)
        shader.use()
        shader.set_uniform_int("u_tex", 0)

        tex_in.bind(0)

        graphics.draw_ui_textured_quad(key)

        graphics.set_depth_test(True)
        graphics.set_depth_mask(True)
