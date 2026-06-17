"""Compatibility re-export for shader interface helpers.

Canonical module: :mod:`termin.render.shader_interface`.
"""

from termin.render.shader_interface import (
    GraphInputSignature,
    PhaseSignature,
    PropertySignature,
    ShaderInterfaceChange,
    UboSignature,
    compare_shader_interface,
    shader_graph_input_signature,
    shader_material_interface_signature,
)

__all__ = [
    "GraphInputSignature",
    "PhaseSignature",
    "PropertySignature",
    "ShaderInterfaceChange",
    "UboSignature",
    "compare_shader_interface",
    "shader_graph_input_signature",
    "shader_material_interface_signature",
]
