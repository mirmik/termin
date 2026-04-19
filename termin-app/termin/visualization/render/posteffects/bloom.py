"""BloomEffect - HDR bloom post-processing effect.

Uses progressive downsampling/upsampling for wide, high-quality bloom.
Based on the approach used in Unreal Engine and Unity.
"""

from tgfx import TcShader
from ..postprocess import PostEffect
from termin.editor.inspect_field import InspectField


# ================================================================
#          BRIGHT PASS - Extract pixels above threshold
# ================================================================

BRIGHT_VERT = """
#version 330 core
layout(location=0) in vec2 a_pos;
layout(location=1) in vec2 a_uv;
out vec2 v_uv;
void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""

BRIGHT_FRAG = """
#version 330 core
in vec2 v_uv;

uniform sampler2D u_texture;
uniform float u_threshold;
uniform float u_soft_threshold;

out vec4 FragColor;

void main() {
    vec3 color = texture(u_texture, v_uv).rgb;

    // Calculate brightness (luminance)
    float brightness = dot(color, vec3(0.2126, 0.7152, 0.0722));

    // Soft threshold with knee
    float knee = u_threshold * u_soft_threshold;
    float soft = brightness - u_threshold + knee;
    soft = clamp(soft, 0.0, 2.0 * knee);
    soft = soft * soft / (4.0 * knee + 0.00001);

    float contribution = max(soft, brightness - u_threshold) / max(brightness, 0.00001);
    contribution = max(contribution, 0.0);

    FragColor = vec4(color * contribution, 1.0);
}
"""

# ================================================================
#          DOWNSAMPLE PASS - 4x4 box filter with bilinear sampling
# ================================================================

DOWNSAMPLE_VERT = """
#version 330 core
layout(location=0) in vec2 a_pos;
layout(location=1) in vec2 a_uv;
out vec2 v_uv;
void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""

DOWNSAMPLE_FRAG = """
#version 330 core
in vec2 v_uv;

uniform sampler2D u_texture;
uniform vec2 u_texel_size;

out vec4 FragColor;

void main() {
    // 13-tap downsample (Karis average style)
    // Reduces fireflies and gives better quality
    vec2 ts = u_texel_size;

    vec3 a = texture(u_texture, v_uv + vec2(-2.0, -2.0) * ts).rgb;
    vec3 b = texture(u_texture, v_uv + vec2( 0.0, -2.0) * ts).rgb;
    vec3 c = texture(u_texture, v_uv + vec2( 2.0, -2.0) * ts).rgb;

    vec3 d = texture(u_texture, v_uv + vec2(-2.0,  0.0) * ts).rgb;
    vec3 e = texture(u_texture, v_uv + vec2( 0.0,  0.0) * ts).rgb;
    vec3 f = texture(u_texture, v_uv + vec2( 2.0,  0.0) * ts).rgb;

    vec3 g = texture(u_texture, v_uv + vec2(-2.0,  2.0) * ts).rgb;
    vec3 h = texture(u_texture, v_uv + vec2( 0.0,  2.0) * ts).rgb;
    vec3 i = texture(u_texture, v_uv + vec2( 2.0,  2.0) * ts).rgb;

    vec3 j = texture(u_texture, v_uv + vec2(-1.0, -1.0) * ts).rgb;
    vec3 k = texture(u_texture, v_uv + vec2( 1.0, -1.0) * ts).rgb;
    vec3 l = texture(u_texture, v_uv + vec2(-1.0,  1.0) * ts).rgb;
    vec3 m = texture(u_texture, v_uv + vec2( 1.0,  1.0) * ts).rgb;

    // Weighted average
    vec3 result = e * 0.125;
    result += (a + c + g + i) * 0.03125;
    result += (b + d + f + h) * 0.0625;
    result += (j + k + l + m) * 0.125;

    FragColor = vec4(result, 1.0);
}
"""

# ================================================================
#          UPSAMPLE PASS - Tent filter (3x3) with additive blend
# ================================================================

UPSAMPLE_VERT = """
#version 330 core
layout(location=0) in vec2 a_pos;
layout(location=1) in vec2 a_uv;
out vec2 v_uv;
void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""

UPSAMPLE_FRAG = """
#version 330 core
in vec2 v_uv;

uniform sampler2D u_texture;      // Lower mip (being upsampled)
uniform sampler2D u_higher_mip;   // Higher mip (to blend with)
uniform vec2 u_texel_size;
uniform float u_blend_factor;     // How much of the upsampled to add

out vec4 FragColor;

void main() {
    // 9-tap tent filter for smooth upsampling
    vec2 ts = u_texel_size;

    vec3 a = texture(u_texture, v_uv + vec2(-1.0, -1.0) * ts).rgb;
    vec3 b = texture(u_texture, v_uv + vec2( 0.0, -1.0) * ts).rgb;
    vec3 c = texture(u_texture, v_uv + vec2( 1.0, -1.0) * ts).rgb;

    vec3 d = texture(u_texture, v_uv + vec2(-1.0,  0.0) * ts).rgb;
    vec3 e = texture(u_texture, v_uv + vec2( 0.0,  0.0) * ts).rgb;
    vec3 f = texture(u_texture, v_uv + vec2( 1.0,  0.0) * ts).rgb;

    vec3 g = texture(u_texture, v_uv + vec2(-1.0,  1.0) * ts).rgb;
    vec3 h = texture(u_texture, v_uv + vec2( 0.0,  1.0) * ts).rgb;
    vec3 i = texture(u_texture, v_uv + vec2( 1.0,  1.0) * ts).rgb;

    // Tent filter weights
    vec3 upsampled = e * 4.0;
    upsampled += (b + d + f + h) * 2.0;
    upsampled += (a + c + g + i);
    upsampled /= 16.0;

    // Blend with higher resolution mip
    vec3 higher = texture(u_higher_mip, v_uv).rgb;

    FragColor = vec4(higher + upsampled * u_blend_factor, 1.0);
}
"""

# ================================================================
#          COMPOSITE PASS - Blend bloom with original
# ================================================================

COMPOSITE_VERT = """
#version 330 core
layout(location=0) in vec2 a_pos;
layout(location=1) in vec2 a_uv;
out vec2 v_uv;
void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""

COMPOSITE_FRAG = """
#version 330 core
in vec2 v_uv;

uniform sampler2D u_original;
uniform sampler2D u_bloom;
uniform float u_intensity;

out vec4 FragColor;

void main() {
    vec3 original = texture(u_original, v_uv).rgb;
    vec3 bloom = texture(u_bloom, v_uv).rgb;

    // Additive blend
    vec3 result = original + bloom * u_intensity;

    FragColor = vec4(result, 1.0);
}
"""


# Lazy-loaded shared shaders
_bright_shader: TcShader | None = None
_downsample_shader: TcShader | None = None
_upsample_shader: TcShader | None = None
_composite_shader: TcShader | None = None


def _get_bright_shader() -> TcShader:
    global _bright_shader
    if _bright_shader is None:
        _bright_shader = TcShader.from_sources(BRIGHT_VERT, BRIGHT_FRAG, "", "BloomBright")
    return _bright_shader


def _get_downsample_shader() -> TcShader:
    global _downsample_shader
    if _downsample_shader is None:
        _downsample_shader = TcShader.from_sources(DOWNSAMPLE_VERT, DOWNSAMPLE_FRAG, "", "BloomDownsample")
    return _downsample_shader


def _get_upsample_shader() -> TcShader:
    global _upsample_shader
    if _upsample_shader is None:
        _upsample_shader = TcShader.from_sources(UPSAMPLE_VERT, UPSAMPLE_FRAG, "", "BloomUpsample")
    return _upsample_shader


def _get_composite_shader() -> TcShader:
    global _composite_shader
    if _composite_shader is None:
        _composite_shader = TcShader.from_sources(COMPOSITE_VERT, COMPOSITE_FRAG, "", "BloomComposite")
    return _composite_shader


class BloomEffect(PostEffect):
    """
    HDR Bloom post-processing effect with progressive downsampling.

    Uses mip-chain approach: downsample -> blur at each level -> upsample.
    This creates wide, smooth bloom with good performance.

    For best results, use with HDR framebuffer (rgba16f format) and
    emission intensity > 1.0 in materials.
    """

    name = "bloom"

    inspect_fields = {
        "threshold": InspectField(
            path="threshold",
            label="Threshold",
            kind="float",
            min=0.0,
            max=10.0,
        ),
        "soft_threshold": InspectField(
            path="soft_threshold",
            label="Soft Knee",
            kind="float",
            min=0.0,
            max=1.0,
        ),
        "intensity": InspectField(
            path="intensity",
            label="Intensity",
            kind="float",
            min=0.0,
            max=5.0,
        ),
        "mip_levels": InspectField(
            path="mip_levels",
            label="Mip Levels",
            kind="int",
            min=1,
            max=8,
        ),
    }

    def __init__(
        self,
        threshold: float = 1.0,
        soft_threshold: float = 0.5,
        intensity: float = 1.0,
        mip_levels: int = 5,
    ):
        self.threshold = threshold
        self.soft_threshold = soft_threshold
        self.intensity = intensity
        self.mip_levels = mip_levels

        # Mip chain: owned native tgfx2 color textures (one per level).
        # Sizes tracked separately so we can reallocate on resize.
        self._mip_texs = []
        self._mip_sizes = []
        self._ctx2_for_destroy = None

    def _ensure_mip_texs(self, ctx2, base_size: tuple[int, int]):
        """Ensure we have native color textures for each mip level."""
        from tgfx._tgfx_native import Tgfx2PixelFormat

        w, h = base_size
        mip_levels = int(self.mip_levels)
        self._ctx2_for_destroy = ctx2

        for i in range(mip_levels):
            mip_w = max(1, w >> i)
            mip_h = max(1, h >> i)

            if i >= len(self._mip_texs):
                tex = ctx2.create_color_attachment(
                    mip_w, mip_h, Tgfx2PixelFormat.RGBA16F,
                )
                self._mip_texs.append(tex)
                self._mip_sizes.append((mip_w, mip_h))
            elif self._mip_sizes[i] != (mip_w, mip_h):
                ctx2.destroy_texture(self._mip_texs[i])
                self._mip_texs[i] = ctx2.create_color_attachment(
                    mip_w, mip_h, Tgfx2PixelFormat.RGBA16F,
                )
                self._mip_sizes[i] = (mip_w, mip_h)

        while len(self._mip_texs) > mip_levels:
            tex = self._mip_texs.pop()
            self._mip_sizes.pop()
            ctx2.destroy_texture(tex)

    def draw(self, ctx2, color_tex2, target_tex2, extra_tex2, size):
        """Execute bloom effect with progressive downsample/upsample via ctx2.

        Intermediate mip chain lives on native tgfx2 color attachments
        owned by this effect.
        """
        from tgfx._tgfx_native import (
            tc_shader_ensure_tgfx2,
            CULL_NONE,
            PIXEL_RGBA16F,
        )

        w, h = size
        mip_levels = int(self.mip_levels)

        self._ensure_mip_texs(ctx2, size)
        mip_tex2 = self._mip_texs

        def _begin(dst_tex2, dst_w, dst_h):
            ctx2.begin_pass(dst_tex2)
            ctx2.set_viewport(0, 0, dst_w, dst_h)
            ctx2.set_depth_test(False)
            ctx2.set_depth_write(False)
            ctx2.set_blend(False)
            ctx2.set_cull(CULL_NONE)

        # === 1. Bright Pass -> mip[0] ===
        bright = _get_bright_shader()
        bright_pair = tc_shader_ensure_tgfx2(ctx2, bright)
        if not bright_pair.vs or not bright_pair.fs:
            return

        _begin(mip_tex2[0], w, h)
        ctx2.bind_shader(bright_pair.vs, bright_pair.fs)
        ctx2.bind_sampled_texture(0, color_tex2)
        ctx2.set_uniform_int("u_texture", 0)
        ctx2.set_uniform_float("u_threshold", self.threshold)
        ctx2.set_uniform_float("u_soft_threshold", self.soft_threshold)
        ctx2.draw_fullscreen_quad()
        ctx2.end_pass()

        # === 2. Progressive Downsample ===
        down = _get_downsample_shader()
        down_pair = tc_shader_ensure_tgfx2(ctx2, down)
        if not down_pair.vs or not down_pair.fs:
            return

        for i in range(1, mip_levels):
            src_w = max(1, w >> (i - 1))
            src_h = max(1, h >> (i - 1))
            dst_w = max(1, w >> i)
            dst_h = max(1, h >> i)

            _begin(mip_tex2[i], dst_w, dst_h)
            ctx2.bind_shader(down_pair.vs, down_pair.fs)
            ctx2.bind_sampled_texture(0, mip_tex2[i - 1])
            ctx2.set_uniform_int("u_texture", 0)
            ctx2.set_uniform_vec2("u_texel_size", 1.0 / max(1, src_w), 1.0 / max(1, src_h))
            ctx2.draw_fullscreen_quad()
            ctx2.end_pass()

        # === 3. Progressive Upsample (accumulate bloom) ===
        up = _get_upsample_shader()
        up_pair = tc_shader_ensure_tgfx2(ctx2, up)
        if not up_pair.vs or not up_pair.fs:
            return

        for i in range(mip_levels - 2, -1, -1):
            src_w = max(1, w >> (i + 1))
            src_h = max(1, h >> (i + 1))
            dst_w = max(1, w >> i)
            dst_h = max(1, h >> i)

            _begin(mip_tex2[i], dst_w, dst_h)
            ctx2.bind_shader(up_pair.vs, up_pair.fs)
            ctx2.bind_sampled_texture(0, mip_tex2[i + 1])
            ctx2.bind_sampled_texture(1, mip_tex2[i])
            ctx2.set_uniform_int("u_texture", 0)
            ctx2.set_uniform_int("u_higher_mip", 1)
            ctx2.set_uniform_vec2("u_texel_size", 1.0 / max(1, src_w), 1.0 / max(1, src_h))
            ctx2.set_uniform_float("u_blend_factor", 1.0)
            ctx2.draw_fullscreen_quad()
            ctx2.end_pass()

        # === 4. Composite: original + bloom -> target_tex2 ===
        comp = _get_composite_shader()
        comp_pair = tc_shader_ensure_tgfx2(ctx2, comp)
        if not comp_pair.vs or not comp_pair.fs:
            return

        _begin(target_tex2, w, h)
        ctx2.bind_shader(comp_pair.vs, comp_pair.fs)
        ctx2.bind_sampled_texture(0, color_tex2)
        ctx2.bind_sampled_texture(1, mip_tex2[0])
        ctx2.set_uniform_int("u_original", 0)
        ctx2.set_uniform_int("u_bloom", 1)
        ctx2.set_uniform_float("u_intensity", self.intensity)
        ctx2.draw_fullscreen_quad()
        ctx2.end_pass()

    def clear_callbacks(self) -> None:
        """Clean up resources."""
        for fbo in self._mip_fbos:
            if fbo is not None:
                fbo.delete()
        self._mip_fbos.clear()
