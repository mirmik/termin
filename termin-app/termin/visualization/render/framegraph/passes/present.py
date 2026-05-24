from __future__ import annotations

from tgfx import TcShader
from termin.render_passes import BlitPass, PresentToScreenPass, ResolvePass

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


def _get_blit_shader() -> TcShader:
    """Get or create the fullscreen quad shader for blitting."""
    global _blit_shader
    if _blit_shader is None:
        _blit_shader = TcShader.from_sources(FSQ_VERT, FSQ_FRAG, "", "BlitShader")
    return _blit_shader


# PresentToScreenPass is imported from termin-render-passes.
# Add _get_shader static method for compatibility with blit code
PresentToScreenPass._get_shader = staticmethod(_get_blit_shader)
