"""TonemapPass - HDR to LDR tonemapping post-processing pass.

Applies tonemapping to convert HDR image to displayable LDR range.
Should be applied after all HDR effects (bloom, etc.) but before UI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.render.framegraph.passes.post_effect_base import PostEffectPass
from termin.visualization.render.shader import ShaderProgram
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import (
        GraphicsBackend,
        FramebufferHandle,
        GPUTextureHandle,
    )


TONEMAP_VERT = """
#version 330 core
layout(location=0) in vec2 a_pos;
layout(location=1) in vec2 a_uv;
out vec2 v_uv;
void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""

TONEMAP_FRAG = """
#version 330 core
in vec2 v_uv;

uniform sampler2D u_input;
uniform float u_exposure;
uniform int u_method;  // 0 = ACES, 1 = Reinhard, 2 = None

out vec4 FragColor;

// ACES Filmic Tone Mapping
// Better highlight rolloff than Reinhard
vec3 aces_tonemap(vec3 x) {
    const float a = 2.51;
    const float b = 0.03;
    const float c = 2.43;
    const float d = 0.59;
    const float e = 0.14;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}

// Reinhard tone mapping
vec3 reinhard_tonemap(vec3 x) {
    return x / (x + vec3(1.0));
}

void main() {
    vec3 color = texture(u_input, v_uv).rgb;

    // Apply exposure
    color *= u_exposure;

    // Apply tonemapping
    if (u_method == 0) {
        color = aces_tonemap(color);
    } else if (u_method == 1) {
        color = reinhard_tonemap(color);
    }
    // method == 2: no tonemapping (passthrough)

    FragColor = vec4(color, 1.0);
}
"""


class TonemapPass(PostEffectPass):
    """
    HDR to LDR tonemapping pass.

    Converts HDR colors to displayable LDR range.
    Should be placed after bloom and before UI rendering.

    Methods:
        - ACES: Film-like response, good highlight rolloff
        - Reinhard: Simple, preserves colors well
        - None: Passthrough (for debugging)
    """

    category = "Effects"

    ACES = 0
    REINHARD = 1
    NONE = 2

    inspect_fields = {
        "exposure": InspectField(
            path="exposure",
            label="Exposure",
            kind="float",
            min=0.1,
            max=10.0,
        ),
        "method": InspectField(
            path="method",
            label="Method",
            kind="int",
            min=0,
            max=2,
        ),
    }

    def __init__(
        self,
        input_res: str = "color",
        output_res: str = "color",
        pass_name: str = "Tonemap",
        exposure: float = 1.0,
        method: int = 0,  # ACES
    ):
        super().__init__(input_res, output_res, pass_name)
        self.exposure = exposure
        self.method = method
        self._shader: ShaderProgram | None = None

    def _get_shader(self) -> ShaderProgram:
        """Lazy-create shader."""
        if self._shader is None:
            self._shader = ShaderProgram(TONEMAP_VERT, TONEMAP_FRAG)
        return self._shader

    def apply(
        self,
        graphics: "GraphicsBackend",
        input_tex: "GPUTextureHandle",
        output_fbo: "FramebufferHandle | None",
        size: tuple[int, int],
        context_key: int,
        reads_fbos: dict[str, "FramebufferHandle | None"],
        scene,
        camera,
    ) -> None:
        """Apply tonemapping."""
        shader = self._get_shader()
        shader.ensure_ready(graphics, context_key)
        shader.use()

        # Bind input texture
        input_tex.bind(0)
        shader.set_uniform_int("u_input", 0)
        shader.set_uniform_float("u_exposure", self.exposure)
        shader.set_uniform_int("u_method", self.method)

        # Draw fullscreen quad
        self.draw_fullscreen_quad(graphics, context_key)

    def destroy(self) -> None:
        """Clean up shader."""
        self._shader = None
