# Pick material for object picking pass

from __future__ import annotations

from termin.geombase import Vec4
from termin.materials import TcMaterial, TcRenderState
from tgfx import TcShader

PICK_SHADER_UUID = "termin-engine-pick-material"


def _load_pick_shader() -> TcShader:
    shader = TcShader.from_builtin_catalog(PICK_SHADER_UUID)
    if not shader.is_valid:
        raise RuntimeError(f"Failed to load built-in shader '{PICK_SHADER_UUID}'")
    return shader


def create_pick_material(name: str = "PickMaterial") -> TcMaterial:
    """Create a pick material for object selection pass."""
    state = TcRenderState.opaque()
    shader = _load_pick_shader()
    mat = TcMaterial.create(name, "")
    mat.shader_name = "PickShader"
    phase = mat.add_phase(shader, "pick", 0)
    phase.state = state
    phase.set_uniform_vec4("u_pickColor", Vec4(1.0, 1.0, 1.0, 1.0))
    return mat


class PickMaterial(TcMaterial):
    """Pick material for object selection. Returns TcMaterial."""

    def __new__(cls) -> TcMaterial:
        return create_pick_material()
