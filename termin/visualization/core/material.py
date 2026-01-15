"""Material and MaterialPhase - re-export from C++.

NOTE: TcMaterial is the new C-based material system.
Material and MaterialPhase are exported as aliases for backwards compatibility
during the migration period.
"""
from termin._native.render import (
    TcMaterial,
    TcMaterialPhase,
    TcRenderState,
    # Old classes (deprecated, use TcMaterial instead)
    Material,
    MaterialPhase,
    get_error_material,
)

# Alias for convenience
MaterialPhaseC = TcMaterialPhase

__all__ = [
    "TcMaterial",
    "TcMaterialPhase",
    "TcRenderState",
    "MaterialPhaseC",
    # Old (deprecated)
    "Material",
    "MaterialPhase",
    "get_error_material",
]
