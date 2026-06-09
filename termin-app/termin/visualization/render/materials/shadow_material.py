"""
Материал для генерации shadow map.

Пишет глубину в стандартный depth buffer, без линеаризации —
используется нативная нелинейная глубина OpenGL для shadow mapping.
"""

from __future__ import annotations

from termin.materials import TcMaterial, TcRenderState
from tgfx import TcShader

SHADOW_SHADER_UUID = "termin-engine-shadow-material"


def _load_shadow_shader() -> TcShader:
    shader = TcShader.from_builtin_catalog(SHADOW_SHADER_UUID)
    if not shader.is_valid:
        raise RuntimeError(f"Failed to load built-in shader '{SHADOW_SHADER_UUID}'")
    return shader


def create_shadow_material(name: str = "ShadowMaterial") -> TcMaterial:
    """Create a shadow pass material."""
    state = TcRenderState.opaque()
    shader = _load_shadow_shader()
    return TcMaterial(
        name=name,
        shader=shader,
        render_state=state,
        phase_mark="shadow",
        priority=0,
        shader_name="ShadowShader",
    )


class ShadowMaterial(TcMaterial):
    """
    Минимальный материал для shadow pass. Returns TcMaterial.

    Рендерит геометрию без освещения и текстур — только позиции.
    Глубина записывается в depth buffer средствами OpenGL.
    """

    def __new__(cls) -> TcMaterial:
        return create_shadow_material()
