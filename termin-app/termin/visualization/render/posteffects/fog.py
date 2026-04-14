from __future__ import annotations

from tgfx import TcShader
from termin.visualization.render.postprocess import PostEffect
from termin.editor.inspect_field import InspectField

FOG_VERT = """
#version 330 core
layout(location = 0) in vec2 a_pos;
layout(location = 1) in vec2 a_uv;
out vec2 v_uv;

void main()
{
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""

FOG_FRAG = """
#version 330 core
in vec2 v_uv;

uniform sampler2D u_color;   // основной цветной рендер (после ColorPass)
uniform sampler2D u_depth;   // depth-карта, сгенерированная DepthPass

uniform vec3  u_fog_color;   // цвет тумана
uniform float u_fog_start;   // нормализованная глубина, с которой начинается туман
uniform float u_fog_end;     // нормализованная глубина, где туман максимален

out vec4 FragColor;

void main()
{
    vec4 base_color = texture(u_color, v_uv);
    float depth = texture(u_depth, v_uv).r; // 0..1 линейная глубина

    // Вычисляем степень тумана: 0 -> нет, 1 -> полностью туман
    float fog_factor = 0.0;
    if (u_fog_end > u_fog_start)
    {
        fog_factor = (depth - u_fog_start) / (u_fog_end - u_fog_start);
        fog_factor = clamp(fog_factor, 0.0, 1.0);
    }

    vec3 fogged = mix(base_color.rgb, u_fog_color, fog_factor);
    FragColor = vec4(fogged, base_color.a);
}
"""


class FogEffect(PostEffect):
    """
    Простой пост-эффект тумана, использующий depth-карту.

    depth-карта — это ресурс FrameGraph с именем, например, "depth",
    который пишет DepthPass.
    """

    name = "fog"

    inspect_fields = {
        "fog_color": InspectField(path="_fog_color", label="Fog Color", kind="color"),
        "fog_start": InspectField(path="_fog_start", label="Fog Start", kind="float", min=0.0, max=1.0, step=0.01),
        "fog_end": InspectField(path="_fog_end", label="Fog End", kind="float", min=0.0, max=1.0, step=0.01),
    }

    def __init__(
        self,
        fog_color=(0.6, 0.7, 0.8),
        fog_start: float = 0.2,
        fog_end: float = 1.0,
    ):
        """
        fog_start / fog_end — в диапазоне [0, 1] по линейной глубине:

            0.0  -> около near
            1.0  -> около far

        При depth < fog_start тумана нет, при depth > fog_end — туман максимален.
        """
        self._fog_color = fog_color
        self._fog_start = float(fog_start)
        self._fog_end = float(fog_end)
        self._shader: TcShader | None = None

    def required_resources(self) -> set[str]:
        return {"depth"}

    def _get_shader(self) -> TcShader:
        if self._shader is None:
            self._shader = TcShader.from_sources(FOG_VERT, FOG_FRAG, "", "FogEffect")
        return self._shader

    def draw(self, ctx2, color_tex2, target_tex2, extra_tex2, size):
        from tgfx._tgfx_native import tc_shader_ensure_tgfx2

        depth_tex2 = extra_tex2.get("depth")

        shader = self._get_shader()
        pair = tc_shader_ensure_tgfx2(ctx2, shader)
        if not pair.vs or not pair.fs:
            return

        def setup(ctx2):
            ctx2.bind_shader(pair.vs, pair.fs)
            ctx2.bind_sampled_texture(0, color_tex2)
            ctx2.set_uniform_int("u_color", 0)

            if depth_tex2 is not None:
                ctx2.bind_sampled_texture(1, depth_tex2)
                ctx2.set_uniform_int("u_depth", 1)

            fc = self._fog_color
            ctx2.set_uniform_vec3("u_fog_color", float(fc[0]), float(fc[1]), float(fc[2]))
            ctx2.set_uniform_float("u_fog_start", self._fog_start if depth_tex2 else 1.0)
            ctx2.set_uniform_float("u_fog_end", self._fog_end if depth_tex2 else 1.0)

            ctx2.draw_fullscreen_quad()

        PostEffect._simple_draw(ctx2, target_tex2, size, setup)
