from __future__ import annotations

from tgfx import TcShader
from termin.render_passes import BlitPass, PresentToScreenPass, ResolvePass

__all__ = ["PresentToScreenPass", "BlitPass", "ResolvePass"]

_PRESENT_BLIT_SHADER_UUID = "termin-engine-present-blit"

_blit_shader: TcShader | None = None


def _get_blit_shader() -> TcShader:
    """Get or create the fullscreen quad shader for blitting."""
    global _blit_shader
    if _blit_shader is None:
        _blit_shader = TcShader.from_builtin_catalog(_PRESENT_BLIT_SHADER_UUID)
    return _blit_shader


# PresentToScreenPass is imported from termin-render-passes.
# Add _get_shader static method for compatibility with blit code
PresentToScreenPass._get_shader = staticmethod(_get_blit_shader)
