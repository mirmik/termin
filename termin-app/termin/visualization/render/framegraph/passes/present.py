from __future__ import annotations

from typing import Set, TYPE_CHECKING

from tgfx import TcShader
from tgfx._tgfx_native import Tgfx2ShaderStage
from termin._native.render import PresentToScreenPass
from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.render.framegraph.execute_context import ExecuteContext

# Re-export C++ PresentToScreenPass
__all__ = ["PresentToScreenPass", "BlitPass", "ResolvePass"]


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
_resolve_msaa_vs = None
_resolve_msaa_fs: dict[tuple[str, int], object] = {}


def _get_blit_shader() -> TcShader:
    """Get or create the fullscreen quad shader for blitting."""
    global _blit_shader
    if _blit_shader is None:
        _blit_shader = TcShader.from_sources(FSQ_VERT, FSQ_FRAG, "", "BlitShader")
    return _blit_shader


RESOLVE_MSAA_VERT = """#version 450 core
layout(location=0) in vec2 a_pos;
layout(location=1) in vec2 a_uv;
layout(location=0) out vec2 v_uv;

void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""


def _make_resolve_msaa_frag(strategy: str, samples: int) -> str:
    combine = "max" if strategy == "max" else "min"
    return f"""#version 450 core
layout(location=0) in vec2 v_uv;
layout(binding=4) uniform sampler2DMS u_tex;
layout(location=0) out vec4 FragColor;

const int SAMPLE_COUNT = {samples};

void main() {{
    ivec2 tex_size = textureSize(u_tex);
    vec2 uv = clamp(v_uv, vec2(0.0), vec2(0.999999));
    ivec2 pixel = ivec2(uv * vec2(tex_size));

    vec4 value = texelFetch(u_tex, pixel, 0);
    for (int i = 1; i < SAMPLE_COUNT; ++i) {{
        value = {combine}(value, texelFetch(u_tex, pixel, i));
    }}

    FragColor = value;
}}
"""


def _get_resolve_msaa_shaders(ctx2, strategy: str, samples: int):
    global _resolve_msaa_vs

    if _resolve_msaa_vs is None:
        _resolve_msaa_vs = ctx2.device.create_shader(Tgfx2ShaderStage.Vertex, RESOLVE_MSAA_VERT)

    key = (strategy, samples)
    fs = _resolve_msaa_fs.get(key)
    if fs is None:
        fs = ctx2.device.create_shader(
            Tgfx2ShaderStage.Fragment,
            _make_resolve_msaa_frag(strategy, samples),
        )
        _resolve_msaa_fs[key] = fs

    return _resolve_msaa_vs, fs


def _normalize_resolve_strategy(value) -> str:
    strategy = str(value).strip().lower()
    if strategy in ("", "average"):
        return "average"
    return strategy


def _normalize_resolve_samples(value: int) -> int | None:
    if value not in (1, 2, 4, 8):
        return None
    return value


class BlitPass(RenderFramePass):
    """
    Копирует color-текстуру из одного FBO в другой через tgfx2 blit.
    """

    category = "Output"

    node_inputs = [("input_res", "fbo"), ("output_res_target", "fbo")]
    node_outputs = [("output_res", "fbo")]
    node_inplace_pairs = [("output_res_target", "output_res")]

    inspect_fields = {
        "input_res": InspectField(path="input_res", label="Input Resource", kind="string"),
        "output_res": InspectField(path="output_res", label="Output Resource", kind="string"),
        "output_res_target": InspectField(path="output_res_target", label="Output Target", kind="string"),
    }

    def __init__(
        self,
        input_res: str = "color",
        output_res: str = "debug",
        pass_name: str = "Blit",
    ):
        super().__init__(pass_name=pass_name)
        self.input_res = input_res
        self.output_res = output_res
        self.output_res_target = ""

    def compute_reads(self) -> Set[str]:
        reads = {self.input_res}
        if self.output_res_target:
            reads.add(self.output_res_target)
        return reads

    def compute_writes(self) -> Set[str]:
        return {self.output_res}

    def get_inplace_aliases(self) -> list[tuple[str, str]]:
        if not self.output_res_target:
            return []
        return [(self.output_res_target, self.output_res)]

    def required_resources(self) -> set[str]:
        return set(self.reads) | set(self.writes)

    def execute(self, ctx: "ExecuteContext") -> None:
        if ctx.ctx2 is None:
            return

        tex_in = ctx.tex2_reads.get(self.input_res)
        tex_out = ctx.tex2_writes.get(self.output_res)
        if not tex_in or not tex_out:
            return

        ctx.ctx2.blit(tex_in, tex_out)


class ResolvePass(RenderFramePass):
    """
    Resolve MSAA FBO в обычный FBO.

    Strategy:
    - average: стандартный backend resolve/blit.
    - min/max: shader resolve для depth-like масок, где обычное усреднение
      MSAA samples меняет смысл данных.
    """

    category = "Output"

    node_inputs = [("input_res", "fbo"), ("output_res_target", "fbo")]
    node_outputs = [("output_res", "fbo")]
    node_inplace_pairs = [("output_res_target", "output_res")]

    inspect_fields = {
        "input_res": InspectField(path="input_res", label="Input Resource", kind="string"),
        "output_res": InspectField(path="output_res", label="Output Resource", kind="string"),
        "output_res_target": InspectField(path="output_res_target", label="Output Target", kind="string"),
        "strategy": InspectField(
            path="strategy",
            label="Strategy",
            kind="enum",
            choices=[
                ("average", "Average"),
                ("min", "Min"),
                ("max", "Max"),
            ],
        ),
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
        self.output_res_target = ""
        self.strategy = "average"

    def compute_reads(self) -> Set[str]:
        reads = {self.input_res}
        if self.output_res_target:
            reads.add(self.output_res_target)
        return reads

    def compute_writes(self) -> Set[str]:
        return {self.output_res}

    def get_inplace_aliases(self) -> list[tuple[str, str]]:
        if not self.output_res_target:
            return []
        return [(self.output_res_target, self.output_res)]

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

        strategy = _normalize_resolve_strategy(self.strategy)
        if strategy == "average":
            ctx.ctx2.blit(tex_in, tex_out)
            return

        if strategy not in ("min", "max"):
            log.error(
                f"[ResolvePass] Unsupported strategy '{self.strategy}' in pass '{self.pass_name}'. "
                "Expected: average, min, max"
            )
            return

        samples = _normalize_resolve_samples(ctx.ctx2.device.texture_sample_count(tex_in))
        if samples is None:
            log.error(
                f"[ResolvePass] Unsupported input sample count in pass '{self.pass_name}'. "
                "Expected: 1, 2, 4, 8"
            )
            return

        if samples == 1:
            ctx.ctx2.blit(tex_in, tex_out)
            return

        from tgfx._tgfx_native import CULL_NONE

        vs, fs = _get_resolve_msaa_shaders(ctx.ctx2, strategy, samples)
        if not vs or not fs:
            log.error(f"[ResolvePass] Failed to create shaders for strategy='{strategy}', samples={samples}")
            return

        _, _, width, height = ctx.render_rect
        width = int(width)
        height = int(height)
        ctx.ctx2.begin_pass(tex_out)
        ctx.ctx2.set_viewport(0, 0, width, height)
        ctx.ctx2.set_depth_test(False)
        ctx.ctx2.set_depth_write(False)
        ctx.ctx2.set_blend(False)
        ctx.ctx2.set_cull(CULL_NONE)
        try:
            ctx.ctx2.bind_shader(vs, fs)
            ctx.ctx2.bind_sampled_texture(4, tex_in)
            ctx.ctx2.draw_fullscreen_quad()
        finally:
            ctx.ctx2.end_pass()



# PresentToScreenPass is now imported from C++ (termin._native.render.PresentToScreenPass)
# Add _get_shader static method for compatibility with blit code
PresentToScreenPass._get_shader = staticmethod(_get_blit_shader)
