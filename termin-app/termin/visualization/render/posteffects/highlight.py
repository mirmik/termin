from __future__ import annotations

import struct

import numpy as np

from termin.visualization.render.postprocess import PostEffect
from termin.visualization.core.picking import id_to_rgb
from termin.editor.inspect_field import InspectField
from tgfx._tgfx_native import Tgfx2ShaderStage


# Push constants carry per-frame highlight parameters (std140 lays them
# out as: vec3 selected_color, float enabled, vec3 outline_color, vec2
# texel_size — 48 bytes total). `#ifdef VULKAN` forks to the native
# push_constant block; on GL the same bytes arrive via tgfx2's ring UBO
# at binding 14.
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

HIGHLIGHT_VERT = "#version 450 core\n" + HIGHLIGHT_PUSH_BLOCK + """
layout(location=0) in vec2 a_pos;
layout(location=1) in vec2 a_uv;
layout(location=0) out vec2 v_uv;

void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
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

# std140 layout for HighlightPushData (48 bytes):
#   offset  0: vec3 u_selected_color (.x, .y, .z at 0, 4, 8)
#   offset 12: float u_enabled       (packs into vec3's vec4 tail slot)
#   offset 16: vec3 u_outline_color  (.x, .y, .z at 16, 20, 24)
#   offset 28: float _pad0           (pad so the next vec2 is aligned to 8)
#   offset 32: vec2 u_texel_size     (.x, .y at 32, 36)
#   offset 40..47: tail pad to 16-byte block boundary.
_HIGHLIGHT_PUSH_FMT = "=12f"  # 12 floats × 4 bytes = 48 bytes
assert struct.calcsize(_HIGHLIGHT_PUSH_FMT) == 48


class HighlightEffect(PostEffect):
    name = "highlight"

    inspect_fields = {
        "color": InspectField(path="_color", label="Outline Color", kind="color"),
    }

    _vs = None
    _fs = None

    def __init__(self, selected_id_getter=None, color=(0.0, 0.0, 0.0, 1.0)):
        """
        selected_id_getter: callable -> int | None
        """
        self._get_id = selected_id_getter
        self._color = color

    def required_resources(self) -> set[str]:
        return {"id"}

    @classmethod
    def _ensure_shaders(cls, ctx2):
        if cls._vs is None:
            cls._vs = ctx2.device.create_shader(Tgfx2ShaderStage.Vertex, HIGHLIGHT_VERT)
        if cls._fs is None:
            cls._fs = ctx2.device.create_shader(Tgfx2ShaderStage.Fragment, HIGHLIGHT_FRAG)

    def draw(self, ctx2, color_tex2, target_tex2, extra_tex2, size):
        w, h = size
        tex_id2 = extra_tex2.get("id")
        selected_id = self._get_id() if self._get_id else 0

        self._ensure_shaders(ctx2)
        if not self._vs or not self._fs:
            return

        enabled = (tex_id2 is not None) and (selected_id > 0)
        if enabled:
            sel_r, sel_g, sel_b = (float(x) for x in id_to_rgb(selected_id))
        else:
            sel_r = sel_g = sel_b = 0.0

        oc = self._color
        texel_x = 1.0 / max(1, w)
        texel_y = 1.0 / max(1, h)

        # Layout: 12 floats matching the std140 offsets documented above.
        # Positions 0..2 = selected_color, 3 = enabled, 4..6 = outline,
        # 7 = pad, 8..9 = texel_size, 10..11 = tail pad.
        push_bytes = struct.pack(
            _HIGHLIGHT_PUSH_FMT,
            sel_r, sel_g, sel_b,
            1.0 if enabled else 0.0,
            float(oc[0]), float(oc[1]), float(oc[2]),
            0.0,
            texel_x, texel_y,
            0.0, 0.0,
        )
        # np.frombuffer returns read-only; nanobind's set_push_constants
        # wants a writable C-contig uint8 ndarray. bytearray copy gives us
        # that without extra fuss.
        push_buf = np.asarray(bytearray(push_bytes), dtype=np.uint8)

        def setup(ctx2):
            ctx2.bind_shader(self._vs, self._fs)
            ctx2.bind_sampled_texture(4, color_tex2)
            # Vulkan's validator requires every shader-declared sampler
            # slot to carry a real descriptor even when the fragment
            # branch skips the sample. Bind the color tex as a harmless
            # placeholder when `enabled == 0` so the id-map slot still
            # has something resolvable.
            id_bind = tex_id2 if tex_id2 is not None else color_tex2
            ctx2.bind_sampled_texture(5, id_bind)
            ctx2.set_push_constants(push_buf)
            ctx2.draw_fullscreen_quad()

        PostEffect._simple_draw(ctx2, target_tex2, size, setup)

    def clear_callbacks(self) -> None:
        """Clear callback to allow garbage collection."""
        self._get_id = None
