"""GrayscalePass - Simple grayscale post-processing pass.

Converts the image to grayscale using luminance weights.
This is a minimal example of a PostEffectPass.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin._native.render import TcShader
from termin.visualization.render.framegraph.passes.post_effect_base import PostEffectPass
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import (
        GraphicsBackend,
        FramebufferHandle,
        GPUTextureHandle,
    )


GRAYSCALE_VERT = """
#version 330 core
layout(location=0) in vec2 a_pos;
layout(location=1) in vec2 a_uv;
out vec2 v_uv;
void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""

GRAYSCALE_FRAG = """
#version 330 core
in vec2 v_uv;

uniform sampler2D u_input;
uniform float u_strength;

out vec4 FragColor;

void main() {
    vec3 color = texture(u_input, v_uv).rgb;

    // Luminance weights (Rec. 709)
    float gray = dot(color, vec3(0.2126, 0.7152, 0.0722));

    // Mix between original and grayscale
    vec3 result = mix(color, vec3(gray), u_strength);

    FragColor = vec4(result, 1.0);
}
"""


class GrayscalePass(PostEffectPass):
    """
    Simple grayscale post-processing pass.

    Converts the image to grayscale with adjustable strength.
    Strength 1.0 = full grayscale, 0.0 = original colors.
    """

    category = "Effects"

    inspect_fields = {
        "strength": InspectField(
            path="strength",
            label="Strength",
            kind="float",
            min=0.0,
            max=1.0,
        ),
    }

    def __init__(
        self,
        input_res: str = "color",
        output_res: str = "color",
        pass_name: str = "Grayscale",
        strength: float = 1.0,
    ):
        super().__init__(input_res, output_res, pass_name)
        self.strength = strength
        self._shader: TcShader | None = None

    def _get_shader(self) -> TcShader:
        """Lazy-create shader."""
        if self._shader is None:
            self._shader = TcShader.from_sources(GRAYSCALE_VERT, GRAYSCALE_FRAG, "", "Grayscale")
        return self._shader

    def apply(
        self,
        graphics: "GraphicsBackend",
        input_tex: "GPUTextureHandle",
        output_fbo: "FramebufferHandle | None",
        size: tuple[int, int],
        reads_fbos: dict[str, "FramebufferHandle | None"],
        scene,
        camera,
    ) -> None:
        """Apply grayscale effect."""
        shader = self._get_shader()
        shader.ensure_ready()
        shader.use()

        # Bind input texture
        input_tex.bind(0)
        shader.set_uniform_int("u_input", 0)
        shader.set_uniform_float("u_strength", self.strength)

        # Draw fullscreen quad
        self.draw_fullscreen_quad(graphics)

    def destroy(self) -> None:
        """Clean up shader."""
        self._shader = None
