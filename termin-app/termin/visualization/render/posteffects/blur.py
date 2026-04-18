import struct

import numpy as np

from termin.visualization.render.postprocess import PostEffect
from termin.editor.inspect_field import InspectField
from tgfx._tgfx_native import Tgfx2ShaderStage


# Backend-neutral Gaussian blur shader pair.
#
# Per-draw parameters (direction + texel_size = 16 bytes) ride on push
# constants on Vulkan; under GL the same bytes land in the std140
# emulation UBO at binding 14 (tgfx2's ring buffer — see
# TGFX2_PUSH_CONSTANTS_BINDING). Same `BlurPushData pc` on both sides,
# so the Python packer does not fork.
BLUR_PUSH_BLOCK = """
struct BlurPushData {
    vec2 u_direction;
    vec2 u_texel_size;
};
#ifdef VULKAN
layout(push_constant) uniform BlurPushBlock { BlurPushData pc; };
#else
layout(std140, binding = 14) uniform BlurPushBlock { BlurPushData pc; };
#endif
"""

GAUSS_VERT = "#version 450 core\n" + BLUR_PUSH_BLOCK + """
layout(location=0) in vec2 a_pos;
layout(location=1) in vec2 a_uv;
layout(location=0) out vec2 v_uv;

void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""

GAUSS_FRAG = "#version 450 core\n" + BLUR_PUSH_BLOCK + """
layout(location=0) in vec2 v_uv;
layout(binding=4) uniform sampler2D u_texture;
layout(location=0) out vec4 FragColor;

// 5-tap gaussian weights (approx sigma=2)
const float w0 = 0.227027;
const float w1 = 0.316216;
const float w2 = 0.070270;

void main() {
    vec2 ts = pc.u_texel_size;
    vec2 dir = pc.u_direction;

    vec3 c = texture(u_texture, v_uv).rgb * w0;
    c += texture(u_texture, v_uv + dir * ts * 1.0).rgb * w1;
    c += texture(u_texture, v_uv - dir * ts * 1.0).rgb * w1;
    c += texture(u_texture, v_uv + dir * ts * 2.0).rgb * w2;
    c += texture(u_texture, v_uv - dir * ts * 2.0).rgb * w2;

    FragColor = vec4(c, 1.0);
}
"""

# std140 packs two vec2 side-by-side (8-byte alignment, each at 8-byte
# stride) with a 16-byte block boundary padding at the end.
_BLUR_PUSH_FMT = "=4f"
assert struct.calcsize(_BLUR_PUSH_FMT) == 16


class GaussianBlurPass(PostEffect):
    """Один проход: горизонтальный или вертикальный."""

    name = "gaussian_blur"

    inspect_fields = {
        "direction": InspectField(
            path="direction",
            label="Direction",
            kind="enum",
            choices=[
                ((1.0, 0.0), "Horizontal"),
                ((0.0, 1.0), "Vertical"),
            ],
        ),
    }

    # Shared across instances: shader compilation is pure and the handles
    # stay valid for the lifetime of the device.
    _vs = None
    _fs = None

    def __init__(self, direction=(1.0, 0.0)):
        self.direction = np.array(direction, dtype=np.float32)

    @classmethod
    def _ensure_shaders(cls, ctx2):
        if cls._vs is None:
            cls._vs = ctx2.device.create_shader(Tgfx2ShaderStage.Vertex, GAUSS_VERT)
        if cls._fs is None:
            cls._fs = ctx2.device.create_shader(Tgfx2ShaderStage.Fragment, GAUSS_FRAG)

    def draw(self, ctx2, color_tex2, target_tex2, extra_tex2, size):
        w, h = size
        texel_x = 1.0 / max(1, w)
        texel_y = 1.0 / max(1, h)

        self._ensure_shaders(ctx2)
        if not self._vs or not self._fs:
            return

        push_bytes = struct.pack(
            _BLUR_PUSH_FMT,
            float(self.direction[0]), float(self.direction[1]),
            texel_x, texel_y,
        )
        push_buf = np.frombuffer(push_bytes, dtype=np.uint8)

        def setup(ctx2):
            ctx2.bind_shader(self._vs, self._fs)
            ctx2.bind_sampled_texture(4, color_tex2)
            ctx2.set_push_constants(push_buf)
            ctx2.draw_fullscreen_quad()

        PostEffect._simple_draw(ctx2, target_tex2, size, setup)
