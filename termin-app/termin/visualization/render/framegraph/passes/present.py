from __future__ import annotations

from typing import Set, TYPE_CHECKING

from tgfx import TcShader
from termin._native.render import PresentToScreenPass
from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.render.framegraph.execute_context import ExecuteContext

# Re-export C++ PresentToScreenPass
__all__ = ["PresentToScreenPass", "BlitPass", "ResolvePass", "blit_fbo_to_fbo"]


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

_blit_shader: TcShader | None = None


def _get_blit_shader() -> TcShader:
    """Get or create the fullscreen quad shader for blitting."""
    global _blit_shader
    if _blit_shader is None:
        _blit_shader = TcShader.from_sources(FSQ_VERT, FSQ_FRAG, "", "BlitShader")
    return _blit_shader


def blit_fbo_to_fbo(
    ctx2,
    src_fb,
    dst_fb,
    size: tuple[int, int],
):
    """
    Copy src_fb's color attachment into dst_fb via a fullscreen quad
    shader. Requires a Tgfx2RenderContext as the first argument.

    When src_fb is not a FramebufferHandle we silently no-op; that
    matches the legacy implementation's ShadowMapArrayResource fallback.
    """
    from termin.visualization.platform.backends.nop_graphics import NOPGraphicsBackend

    if isinstance(ctx2, NOPGraphicsBackend):
        return

    _blit_fbo_to_fbo_tgfx2(ctx2, src_fb, dst_fb, size)


def _blit_fbo_to_fbo_tgfx2(ctx2, src_fb, dst_fb, size):
    """ctx2 variant of blit_fbo_to_fbo — fullscreen blit through
    RenderContext2. src_fb and dst_fb are legacy FramebufferHandles;
    they get wrapped as external tgfx2 textures for the duration of
    this draw."""
    from tgfx._tgfx_native import (
        tc_shader_ensure_tgfx2,
        wrap_fbo_color_as_tgfx2,
        CULL_NONE,
        PIXEL_RGBA8,
    )
    from termin.graphics import FramebufferHandle

    if not isinstance(src_fb, FramebufferHandle):
        return
    if not isinstance(dst_fb, FramebufferHandle):
        return

    w, h = size
    src_tex2 = wrap_fbo_color_as_tgfx2(ctx2, src_fb)
    dst_tex2 = wrap_fbo_color_as_tgfx2(ctx2, dst_fb)
    if not src_tex2 or not dst_tex2:
        return

    shader = _get_blit_shader()
    pair = tc_shader_ensure_tgfx2(ctx2, shader)
    if not pair.vs or not pair.fs:
        return

    ctx2.begin_pass(dst_tex2)
    ctx2.set_viewport(0, 0, w, h)
    ctx2.set_depth_test(False)
    ctx2.set_depth_write(False)
    ctx2.set_blend(False)
    ctx2.set_cull(CULL_NONE)
    ctx2.set_color_format(PIXEL_RGBA8)
    ctx2.bind_shader(pair.vs, pair.fs)
    ctx2.bind_sampled_texture(0, src_tex2)
    ctx2.set_uniform_int("u_tex", 0)
    ctx2.draw_fullscreen_quad()
    ctx2.end_pass()


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
        from tcbase import log

        if ctx.ctx2 is None:
            log.error("[ResolvePass] ctx.ctx2 is None — ResolvePass is tgfx2-only")
            return

        tex_in = ctx.tex2_reads.get(self.input_res)
        tex_out = ctx.tex2_writes.get(self.output_res)
        if not tex_in or not tex_out:
            log.warn(
                f"[ResolvePass] Missing tex2: input={bool(tex_in)}, output={bool(tex_out)}, "
                f"input_res='{self.input_res}', output_res='{self.output_res}'"
            )
            return

        ctx.ctx2.blit(tex_in, tex_out)



# PresentToScreenPass is now imported from C++ (termin._native.render.PresentToScreenPass)
# Add _get_shader static method for compatibility with blit code
PresentToScreenPass._get_shader = staticmethod(_get_blit_shader)
