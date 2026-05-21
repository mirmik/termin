from __future__ import annotations

import struct
from typing import Callable, Set

import numpy as np

from termin.inspect import InspectField
from termin.render_framework.python_pass import PythonFramePass
from termin.visualization.core.picking import id_to_rgb
from tgfx._tgfx_native import CULL_NONE, Tgfx2ShaderHandle, Tgfx2ShaderStage


HIGHLIGHT_PUSH_BLOCK = """
struct HighlightPushData {
    vec3  u_selected_color;
    float u_enabled;
    vec3  u_outline_color;
    float _pad0;
    vec2  u_texel_size;
};
#ifdef VULKAN
layout(push_constant) uniform HighlightPushBlock { HighlightPushData pc; };
#else
layout(std140, binding = 14) uniform HighlightPushBlock { HighlightPushData pc; };
#endif
"""


HIGHLIGHT_FRAG = "#version 450 core\n" + HIGHLIGHT_PUSH_BLOCK + """
layout(location=0) in vec2 v_uv;
layout(binding=4) uniform sampler2D u_color;
layout(binding=5) uniform sampler2D u_id;
layout(location=0) out vec4 FragColor;

float is_selected(vec3 id_color) {
    float d = distance(id_color, pc.u_selected_color);
    return float(d < 0.001);
}

void main() {
    vec4 base = texture(u_color, v_uv);

    if (pc.u_enabled < 0.5) {
        FragColor = base;
        return;
    }

    vec3 id_center = texture(u_id, v_uv).rgb;
    float center_sel = is_selected(id_center);

    vec2 ts = pc.u_texel_size;
    float neigh_sel = 0.0;
    neigh_sel = max(neigh_sel, is_selected(texture(u_id, v_uv + vec2( ts.x,  0.0)).rgb));
    neigh_sel = max(neigh_sel, is_selected(texture(u_id, v_uv + vec2(-ts.x,  0.0)).rgb));
    neigh_sel = max(neigh_sel, is_selected(texture(u_id, v_uv + vec2( 0.0,  ts.y)).rgb));
    neigh_sel = max(neigh_sel, is_selected(texture(u_id, v_uv + vec2( 0.0, -ts.y)).rgb));

    float outline = 0.0;
    outline = max(outline, center_sel * (1.0 - neigh_sel));
    outline = max(outline, neigh_sel * (1.0 - center_sel));

    if (outline > 0.0) {
        float k = 0.8;
        vec3 col = mix(base.rgb, pc.u_outline_color, k);
        FragColor = vec4(col, base.a);
    } else {
        FragColor = base;
    }
}
"""


_HIGHLIGHT_PUSH_FMT = "=12f"
assert struct.calcsize(_HIGHLIGHT_PUSH_FMT) == 48


class HighlightPass(PythonFramePass):
    category = "Effects"

    node_inputs = [("input_res", "fbo"), ("id_res", "fbo")]
    node_outputs = [("output_res", "fbo")]

    inspect_fields = {
        "input_res": InspectField(path="input_res", label="Input Resource", kind="string"),
        "id_res": InspectField(path="id_res", label="ID Resource", kind="string"),
        "output_res": InspectField(path="output_res", label="Output Resource", kind="string"),
        "color": InspectField(path="color", label="Outline Color", kind="color"),
    }

    _fs = None

    def __init__(
        self,
        selected_id_getter: Callable[[], int | None] | None = None,
        color=(0.0, 0.0, 0.0, 1.0),
        input_res: str = "color",
        id_res: str = "id",
        output_res: str = "color_highlight",
        pass_name: str = "Highlight",
    ) -> None:
        super().__init__(pass_name=pass_name)
        self.input_res = input_res
        self.id_res = id_res
        self.output_res = output_res
        self.color = color
        self._get_id = selected_id_getter

    def compute_reads(self) -> Set[str]:
        return {self.input_res, self.id_res}

    def compute_writes(self) -> Set[str]:
        return {self.output_res}

    @classmethod
    def _ensure_shader(cls, ctx2) -> None:
        if cls._fs is None:
            cls._fs = ctx2.device.create_shader(Tgfx2ShaderStage.Fragment, HIGHLIGHT_FRAG)

    def _selected_id(self) -> int:
        if self._get_id is None:
            return 0
        selected_id = self._get_id()
        return int(selected_id) if selected_id is not None else 0

    def execute(self, ctx) -> None:
        from tcbase import log

        if ctx.ctx2 is None:
            log.error("[HighlightPass] ctx.ctx2 is None — pass is tgfx2-only")
            return

        color_tex2 = ctx.tex2_reads.get(self.input_res)
        target_tex2 = ctx.tex2_writes.get(self.output_res)
        if not color_tex2 or not target_tex2:
            log.warn(
                f"[HighlightPass] Missing tex2: input={bool(color_tex2)}, output={bool(target_tex2)}, "
                f"input_res='{self.input_res}', output_res='{self.output_res}'"
            )
            return

        ctx2 = ctx.ctx2
        self._ensure_shader(ctx2)
        if not self._fs:
            log.error("[HighlightPass] fragment shader was not created")
            return

        tex_id2 = ctx.tex2_reads.get(self.id_res)
        selected_id = self._selected_id()
        enabled = tex_id2 is not None and selected_id > 0

        if enabled:
            sel_r, sel_g, sel_b = (float(x) for x in id_to_rgb(selected_id))
        else:
            sel_r = sel_g = sel_b = 0.0

        _, _, w, h = ctx.render_rect
        texel_x = 1.0 / max(1, int(w))
        texel_y = 1.0 / max(1, int(h))
        outline = self.color
        push_bytes = struct.pack(
            _HIGHLIGHT_PUSH_FMT,
            sel_r, sel_g, sel_b,
            1.0 if enabled else 0.0,
            float(outline[0]), float(outline[1]), float(outline[2]),
            0.0,
            texel_x, texel_y,
            0.0, 0.0,
        )
        push_buf = np.asarray(bytearray(push_bytes), dtype=np.uint8)

        ctx2.begin_pass(target_tex2)
        ctx2.set_viewport(0, 0, int(w), int(h))
        ctx2.set_depth_test(False)
        ctx2.set_depth_write(False)
        ctx2.set_blend(False)
        ctx2.set_cull(CULL_NONE)
        try:
            ctx2.bind_shader(Tgfx2ShaderHandle(), self._fs)
            ctx2.bind_sampled_texture(4, color_tex2)
            id_bind = tex_id2 if tex_id2 is not None else color_tex2
            ctx2.bind_sampled_texture(5, id_bind)
            ctx2.set_push_constants(push_buf)
            ctx2.draw_fullscreen_quad()
        finally:
            ctx2.end_pass()

    def clear_callbacks(self) -> None:
        self._get_id = None
