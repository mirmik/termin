"""BloomEffect - HDR bloom post-processing effect.

Uses progressive downsampling/upsampling for wide, high-quality bloom.
Based on the approach used in Unreal Engine and Unity.
"""

import numpy as np
from ..shader import ShaderProgram
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
        """
        Args:
            threshold: Brightness threshold for bloom extraction.
            soft_threshold: Soft knee (0-1) for smoother threshold transition.
            intensity: Bloom intensity multiplier.
            mip_levels: Number of downsample levels (more = wider bloom).
                        5 levels = 1/32 resolution at lowest = very wide bloom.
        """

        self.threshold = threshold
        self.soft_threshold = soft_threshold
        self.intensity = intensity
        self.mip_levels = mip_levels

        # Shaders
        self._bright_shader = ShaderProgram(BRIGHT_VERT, BRIGHT_FRAG)
        self._downsample_shader = ShaderProgram(DOWNSAMPLE_VERT, DOWNSAMPLE_FRAG)
        self._upsample_shader = ShaderProgram(UPSAMPLE_VERT, UPSAMPLE_FRAG)
        self._composite_shader = ShaderProgram(COMPOSITE_VERT, COMPOSITE_FRAG)

        # Mip chain FBOs
        self._mip_fbos = []

    def _ensure_mip_fbos(self, graphics, base_size: tuple[int, int], format_str: str):
        """Ensure we have FBOs for each mip level."""
        w, h = base_size
        mip_levels = int(self.mip_levels)

        # Create/resize FBOs for each mip level
        for i in range(mip_levels):
            mip_w = max(1, w >> i)
            mip_h = max(1, h >> i)

            if i >= len(self._mip_fbos):
                fbo = graphics.create_framebuffer((mip_w, mip_h), 1, format_str)
                self._mip_fbos.append(fbo)
            else:
                self._mip_fbos[i].resize(mip_w, mip_h)

        # Remove excess FBOs if mip_levels decreased
        while len(self._mip_fbos) > mip_levels:
            fbo = self._mip_fbos.pop()
            fbo.delete()

    def draw(self, gfx, context_key, color_tex, extra_textures, size, target_fbo=None):
        """Execute bloom effect with progressive downsample/upsample."""
        w, h = size
        format_str = "rgba16f"
        mip_levels = int(self.mip_levels)

        self._ensure_mip_fbos(gfx, size, format_str)

        # Disable depth testing for post-processing
        gfx.set_depth_test(False)
        gfx.set_blend(False)

        # === 1. Bright Pass -> mip[0] ===
        mip0 = self._mip_fbos[0]
        gfx.bind_framebuffer(mip0)
        gfx.set_viewport(0, 0, w, h)

        self._bright_shader.ensure_ready(gfx, context_key)
        self._bright_shader.use()

        color_tex.bind(0)
        self._bright_shader.set_uniform_int("u_texture", 0)
        self._bright_shader.set_uniform_float("u_threshold", self.threshold)
        self._bright_shader.set_uniform_float("u_soft_threshold", self.soft_threshold)

        gfx.draw_ui_textured_quad(context_key)

        # === 2. Progressive Downsample ===
        self._downsample_shader.ensure_ready(gfx, context_key)
        self._downsample_shader.use()

        for i in range(1, mip_levels):
            src_fbo = self._mip_fbos[i - 1]
            dst_fbo = self._mip_fbos[i]

            src_w = max(1, w >> (i - 1))
            src_h = max(1, h >> (i - 1))
            dst_w = max(1, w >> i)
            dst_h = max(1, h >> i)

            gfx.bind_framebuffer(dst_fbo)
            gfx.set_viewport(0, 0, dst_w, dst_h)

            src_fbo.color_texture().bind(0)
            self._downsample_shader.set_uniform_int("u_texture", 0)
            self._downsample_shader.set_uniform_auto(
                "u_texel_size",
                np.array([1.0 / max(1, src_w), 1.0 / max(1, src_h)], dtype=np.float32)
            )

            gfx.draw_ui_textured_quad(context_key)

        # === 3. Progressive Upsample (accumulate bloom) ===
        self._upsample_shader.ensure_ready(gfx, context_key)
        self._upsample_shader.use()

        for i in range(mip_levels - 2, -1, -1):
            src_fbo = self._mip_fbos[i + 1]  # Lower mip (upsampling from)
            dst_fbo = self._mip_fbos[i]      # Higher mip (upsampling to)

            src_w = max(1, w >> (i + 1))
            src_h = max(1, h >> (i + 1))
            dst_w = max(1, w >> i)
            dst_h = max(1, h >> i)

            gfx.bind_framebuffer(dst_fbo)
            gfx.set_viewport(0, 0, dst_w, dst_h)

            src_fbo.color_texture().bind(0)
            dst_fbo.color_texture().bind(1)

            self._upsample_shader.set_uniform_int("u_texture", 0)
            self._upsample_shader.set_uniform_int("u_higher_mip", 1)
            self._upsample_shader.set_uniform_auto(
                "u_texel_size",
                np.array([1.0 / max(1, src_w), 1.0 / max(1, src_h)], dtype=np.float32)
            )
            self._upsample_shader.set_uniform_float("u_blend_factor", 1.0)

            gfx.draw_ui_textured_quad(context_key)

        # === 4. Composite Pass ===
        if target_fbo is not None:
            gfx.bind_framebuffer(target_fbo)
            gfx.set_viewport(0, 0, w, h)

        self._composite_shader.ensure_ready(gfx, context_key)
        self._composite_shader.use()

        color_tex.bind(0)
        self._mip_fbos[0].color_texture().bind(1)

        self._composite_shader.set_uniform_int("u_original", 0)
        self._composite_shader.set_uniform_int("u_bloom", 1)
        self._composite_shader.set_uniform_float("u_intensity", self.intensity)

        gfx.draw_ui_textured_quad(context_key)

    def clear_callbacks(self) -> None:
        """Clean up resources."""
        for fbo in self._mip_fbos:
            if fbo is not None:
                fbo.delete()
        self._mip_fbos.clear()
