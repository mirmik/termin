from __future__ import annotations

from termin.materials import TcMaterial, TcRenderState
from tgfx import TcShader

DEPTH_SHADER_UUID = "termin-engine-depth-material"


def _load_depth_shader() -> TcShader:
    shader = TcShader.from_builtin_catalog(DEPTH_SHADER_UUID)
    if not shader.is_valid:
        raise RuntimeError(f"Failed to load built-in shader '{DEPTH_SHADER_UUID}'")
    return shader


def create_depth_material(
    near: float = 0.1,
    far: float = 100.0,
    name: str = "DepthMaterial",
) -> TcMaterial:
    """Create a depth material that writes linear depth to color channel."""
    state = TcRenderState.opaque()
    shader = _load_depth_shader()
    mat = TcMaterial(
        name=name,
        shader=shader,
        render_state=state,
        phase_mark="depth",
        priority=0,
        shader_name="DepthShader",
    )

    phase = mat.default_phase()
    if phase is not None:
        phase.set_uniform_float("u_near", near)
        phase.set_uniform_float("u_far", far)

    return mat


class DepthMaterial(TcMaterial):
    """
    Простой материал, который пишет линейную глубину в канал цвета.
    Returns TcMaterial.
    """

    def __new__(cls) -> TcMaterial:
        return create_depth_material()
