from __future__ import annotations

from typing import Set, TYPE_CHECKING

from termin._native.render import TcShader
from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.render.framegraph.execute_context import ExecuteContext


def _get_texture_from_resource(resource, shadow_map_index: int = 0):
    """
    Извлекает текстуру из ресурса framegraph для отображения.

    Поддерживает:
    - SingleFBO: возвращает color_texture()
    - ShadowMapArrayResource: возвращает текстуру из первого entry (или по индексу)
    - FramebufferHandle (C++): возвращает color_texture()

    Args:
        resource: объект ресурса (SingleFBO, ShadowMapArrayResource, FramebufferHandle)
        shadow_map_index: индекс shadow map для ShadowMapArrayResource

    Returns:
        GPUTextureHandle или None
    """
    if resource is None:
        return None

    from termin.visualization.render.framegraph.resource import (
        SingleFBO,
        ShadowMapArrayResource,
    )
    from termin.graphics import FramebufferHandle

    if isinstance(resource, ShadowMapArrayResource):
        if len(resource) == 0:
            return None
        index = min(shadow_map_index, len(resource) - 1)
        entry = resource[index]
        return entry.texture()

    if isinstance(resource, SingleFBO):
        return resource.color_texture()

    if isinstance(resource, FramebufferHandle):
        return resource.color_texture()

    return None


def blit_fbo_to_fbo(
    gfx: "GraphicsBackend",
    src_fb,
    dst_fb,
    size: tuple[int, int],
):
    from termin.visualization.platform.backends.nop_graphics import NOPGraphicsBackend

    # Для NOP бэкенда пропускаем реальные OpenGL операции
    if isinstance(gfx, NOPGraphicsBackend):
        return

    w, h = size

    # целевой FBO
    gfx.bind_framebuffer(dst_fb)
    gfx.set_viewport(0, 0, w, h)

    # глубина нам не нужна
    gfx.set_depth_test(False)
    gfx.set_depth_mask(False)

    # берём ту же фуллскрин-квад-программу, что и PresentToScreenPass
    shader = PresentToScreenPass._get_shader()
    shader.ensure_ready()
    shader.use()
    shader.set_uniform_int("u_tex", 0)

    # Извлекаем текстуру с учетом типа ресурса
    tex = _get_texture_from_resource(src_fb)
    if tex is None:
        # Если не удалось получить текстуру, ничего не делаем
        gfx.set_depth_test(True)
        gfx.set_depth_mask(True)
        return

    tex.bind(0)

    gfx.draw_ui_textured_quad()

    gfx.set_depth_test(True)
    gfx.set_depth_mask(True)


class BlitPass(RenderFramePass):
    """
    Копирует color-текстуру из одного FBO в другой через фуллскрин-квад.
    Источник задаётся колбэком get_source_res, чтобы его можно было
    динамически переключать из редактора/дебагера.

    Для отключения пасса используйте enabled=False.

    Note: get_source_res — runtime callback, не сериализуется.
    При десериализации нужно задать его отдельно.
    """

    category = "Output"

    node_inputs = [("input_res", "fbo")]
    node_outputs = [("output_res", "fbo")]

    def __init__(
        self,
        get_source_res=None,
        output_res: str = "debug",
        pass_name: str = "Blit",
    ):
        super().__init__(pass_name=pass_name)
        self._get_source_res = get_source_res
        self.output_res = output_res
        self._current_src_name: str | None = None

    def compute_reads(self) -> Set[str]:
        if self._get_source_res is None:
            return set()
        src_name = self._get_source_res()
        if src_name:
            self._current_src_name = src_name
            return {src_name}
        self._current_src_name = None
        return set()

    def compute_writes(self) -> Set[str]:
        return {self.output_res}

    def required_resources(self) -> set[str]:
        return set(self.reads) | set(self.writes)

    def execute(self, ctx: "ExecuteContext") -> None:
        px, py, pw, ph = ctx.rect

        if self._get_source_res is None:
            return

        src_name = self._get_source_res()
        if not src_name:
            return

        fb_in = ctx.reads_fbos.get(src_name)
        if fb_in is None:
            return

        fb_out = ctx.writes_fbos.get(self.output_res)
        if fb_out is None:
            return

        blit_fbo_to_fbo(ctx.graphics, fb_in, fb_out, (pw, ph))


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


class ResolvePass(RenderFramePass):
    """
    Resolve MSAA FBO в обычный FBO через glBlitFramebuffer.

    Необходим перед любым pass'ом, который сэмплирует текстуру (PostProcess и др.),
    если источник — MSAA FBO.
    """

    category = "Output"

    node_inputs = [("input_res", "fbo")]
    node_outputs = [("output_res", "fbo")]

    inspect_fields = {
        "input_res": InspectField(path="input_res", label="Input Resource", kind="string"),
        "output_res": InspectField(path="output_res", label="Output Resource", kind="string"),
    }

    def __init__(
        self,
        input_res: str = "color",
        output_res: str = "resolved",
        pass_name: str = "Resolve",
    ):
        super().__init__(pass_name=pass_name)
        self.input_res = input_res
        self.output_res = output_res

    def compute_reads(self) -> Set[str]:
        return {self.input_res}

    def compute_writes(self) -> Set[str]:
        return {self.output_res}

    def execute(self, ctx: "ExecuteContext") -> None:
        from termin.visualization.platform.backends.nop_graphics import NOPGraphicsBackend
        from termin._native import log
        from termin.graphics import FramebufferHandle

        if isinstance(ctx.graphics, NOPGraphicsBackend):
            return

        px, py, pw, ph = ctx.rect

        fb_in = ctx.reads_fbos.get(self.input_res)
        fb_out = ctx.writes_fbos.get(self.output_res)
        if fb_in is None or fb_out is None:
            log.warn(f"[ResolvePass] Missing FBO: input={fb_in is not None}, output={fb_out is not None}, input_res='{self.input_res}', output_res='{self.output_res}'")
            return

        # Check type - skip if not a FramebufferHandle
        if not isinstance(fb_in, FramebufferHandle):
            log.warn(f"[ResolvePass] input '{self.input_res}' is {type(fb_in).__name__}, not FramebufferHandle")
            return
        if not isinstance(fb_out, FramebufferHandle):
            log.warn(f"[ResolvePass] output '{self.output_res}' is {type(fb_out).__name__}, not FramebufferHandle")
            return

        src_size = fb_in.get_size()
        ctx.graphics.blit_framebuffer(
            fb_in,
            fb_out,
            (0, 0, src_size[0], src_size[1]),
            (0, 0, pw, ph),
        )


class PresentToScreenPass(RenderFramePass):
    """
    Берёт текстуру из ресурса input_res и выводит её на экран
    фуллскрин-квадом.
    """

    category = "Output"

    node_inputs = [("input_res", "fbo")]
    node_outputs = []  # Output is screen, not a resource

    inspect_fields = {
        "input_res": InspectField(path="input_res", label="Input Resource", kind="string"),
        "output_res": InspectField(path="output_res", label="Output Resource", kind="string"),
    }

    _shader: TcShader | None = None

    def __init__(self, input_res: str = "color", output_res: str = "DISPLAY", pass_name: str = "PresentToScreen"):
        super().__init__(pass_name=pass_name)
        self.input_res = input_res
        self.output_res = output_res

    def compute_reads(self) -> Set[str]:
        return {self.input_res}

    def compute_writes(self) -> Set[str]:
        return {self.output_res}

    @classmethod
    def _get_shader(cls) -> TcShader:
        if cls._shader is None:
            cls._shader = TcShader.from_sources(FSQ_VERT, FSQ_FRAG, "", "PresentToScreen")
        return cls._shader

    def execute(self, ctx: "ExecuteContext") -> None:
        from termin.visualization.platform.backends.nop_graphics import NOPGraphicsBackend

        # Для NOP бэкенда пропускаем реальные OpenGL операции
        if isinstance(ctx.graphics, NOPGraphicsBackend):
            return

        px, py, pw, ph = ctx.rect

        fb_in = ctx.reads_fbos.get(self.input_res)
        fb_out = ctx.writes_fbos.get("DISPLAY")
        if fb_in is None or fb_out is None:
            return

        # Используем glBlitFramebuffer — работает и для обычных FBO, и для MSAA (resolve)
        src_size = fb_in.get_size()
        ctx.graphics.blit_framebuffer(
            fb_in,
            fb_out,
            (0, 0, src_size[0], src_size[1]),
            (px, py, px + pw, py + ph),
        )
