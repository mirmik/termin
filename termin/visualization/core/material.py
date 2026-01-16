"""Material and MaterialPhase - re-export from C++.

TcMaterial is the C-based material system.
Material and MaterialPhase are now aliases to TcMaterial/TcMaterialPhase.
"""
from termin._native.render import (
    TcMaterial,
    TcMaterialPhase,
    TcRenderState,
)

# Backwards compatibility aliases
Material = TcMaterial
MaterialPhase = TcMaterialPhase
MaterialPhaseC = TcMaterialPhase

__all__ = [
    "TcMaterial",
    "TcMaterialPhase",
    "TcRenderState",
    # Aliases for backwards compatibility
    "Material",
    "MaterialPhase",
    "MaterialPhaseC",
]
