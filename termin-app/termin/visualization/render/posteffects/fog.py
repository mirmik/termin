from __future__ import annotations

import struct

import numpy as np

from termin.visualization.render.postprocess import PostEffect
from termin.editor.inspect_field import InspectField
from tgfx._tgfx_native import Tgfx2ShaderStage


# Push constants carry the per-draw fog params (24 bytes, padded to 32
# by std140's vec3 → 16-byte alignment rule). `#ifdef VULKAN` selects
# the native push_constant block; under GL the same bytes come in via
# tgfx2's ring UBO at binding 14.
FOG_PUSH_BLOCK = """
struct FogPushData {
    vec3  u_fog_color;
    float u_fog_start;
    float u_fog_end;
};
#ifdef VULKAN
layout(push_constant) uniform FogPushBlock { FogPushData pc; };
#else
layout(std140, binding = 14) uniform FogPushBlock { FogPushData pc; };
#endif
"""

FOG_VERT = "#version 450 core\n" + FOG_PUSH_BLOCK + """
layout(location = 0) in vec2 a_pos;
layout(location = 1) in vec2 a_uv;
layout(location = 0) out vec2 v_uv;

void main()
{
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""

FOG_FRAG = "#version 450 core\n" + FOG_PUSH_BLOCK + """
layout(location = 0) in vec2 v_uv;
layout(binding = 4) uniform sampler2D u_color;
layout(binding = 5) uniform sampler2D u_depth;
layout(location = 0) out vec4 FragColor;

void main()
{
    vec4 base_color = texture(u_color, v_uv);
    float depth = texture(u_depth, v_uv).r;  // 0..1 linear depth

    float fog_factor = 0.0;
    if (pc.u_fog_end > pc.u_fog_start) {
        fog_factor = (depth - pc.u_fog_start) / (pc.u_fog_end - pc.u_fog_start);
        fog_factor = clamp(fog_factor, 0.0, 1.0);
    }

    vec3 fogged = mix(base_color.rgb, pc.u_fog_color, fog_factor);
    FragColor = vec4(fogged, base_color.a);
}
"""

# std140: vec3 (offset 0, size 12), float (offset 12, fits in the
# vec4-aligned slot 0), float (offset 16, size 4), tail pad to 32.
_FOG_PUSH_FMT = "=3f f f 3x"  # 3f + float + float + 3 bytes pad
# Actually simpler: 8 floats laid out explicitly to stay independent
# of struct padding guesswork.
_FOG_PUSH_FMT = "=8f"
assert struct.calcsize(_FOG_PUSH_FMT) == 32


class FogEffect(PostEffect):
    """Height/depth-based fog post-effect."""

    name = "fog"

    inspect_fields = {
        "fog_color": InspectField(path="_fog_color", label="Fog Color", kind="color"),
        "fog_start": InspectField(path="_fog_start", label="Fog Start", kind="float", min=0.0, max=1.0, step=0.01),
        "fog_end": InspectField(path="_fog_end", label="Fog End", kind="float", min=0.0, max=1.0, step=0.01),
    }

    _vs = None
    _fs = None

    def __init__(
        self,
        fog_color=(0.6, 0.7, 0.8),
        fog_start: float = 0.2,
        fog_end: float = 1.0,
    ):
        self._fog_color = fog_color
        self._fog_start = float(fog_start)
        self._fog_end = float(fog_end)

    def required_resources(self) -> set[str]:
        return {"depth"}

    @classmethod
    def _ensure_shaders(cls, ctx2):
        if cls._vs is None:
            cls._vs = ctx2.device.create_shader(Tgfx2ShaderStage.Vertex, FOG_VERT)
        if cls._fs is None:
            cls._fs = ctx2.device.create_shader(Tgfx2ShaderStage.Fragment, FOG_FRAG)

    def draw(self, ctx2, color_tex2, target_tex2, extra_tex2, size):
        depth_tex2 = extra_tex2.get("depth")

        self._ensure_shaders(ctx2)
        if not self._vs or not self._fs:
            return

        # When depth is missing we still run the shader (need a bound
        # sampler for Vulkan's validator), but fall back to start=end=1
        # so the fog factor collapses to 0 and the frame passes through.
        fc = self._fog_color
        start = self._fog_start if depth_tex2 is not None else 1.0
        end = self._fog_end if depth_tex2 is not None else 1.0
        push_bytes = struct.pack(
            _FOG_PUSH_FMT,
            float(fc[0]), float(fc[1]), float(fc[2]),
            start,  # aligned to offset 12 in vec3's vec4 slot? No — std140
            end,    # wants vec3 at 0, float at 12 (fits vec4 slot 0 tail),
            0.0,    # then floats go at 16, 20. We pad to 32 with zeroes.
            0.0,
            0.0,
        )
        # std140 layout verification: offsets are
        #   u_fog_color .x .y .z  : 0, 4, 8
        #   u_fog_start           : 12
        #   u_fog_end             : 16
        # The pack above places start at offset 12 (after 3 floats, position
        # 3 in the `=8f` stream) and end at offset 16 (position 4). Good.
        # bytearray → writable C-contig ndarray (nanobind rejects read-only).
        push_buf = np.asarray(bytearray(push_bytes), dtype=np.uint8)

        def setup(ctx2):
            ctx2.bind_shader(self._vs, self._fs)
            ctx2.bind_sampled_texture(4, color_tex2)
            if depth_tex2 is not None:
                ctx2.bind_sampled_texture(5, depth_tex2)
            else:
                # No depth attachment in the framegraph this frame — bind
                # the color tex again as a harmless placeholder so the
                # Vulkan validator doesn't complain about an empty slot.
                ctx2.bind_sampled_texture(5, color_tex2)
            ctx2.set_push_constants(push_buf)
            ctx2.draw_fullscreen_quad()

        PostEffect._simple_draw(ctx2, target_tex2, size, setup)
