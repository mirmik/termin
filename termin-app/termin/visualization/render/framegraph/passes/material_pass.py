"""MaterialPass - Post-processing pass using a Material asset.

Re-exports C++ MaterialPass with Python-only utilities for editor.
"""

from __future__ import annotations

from typing import List, Tuple

from termin.render_components import MaterialPass
from termin.inspect import InspectField
from tcbase import log

__all__ = ["MaterialPass", "get_texture_inputs_for_material"]

# Add inspect_fields to C++ class for editor integration
# Key must match the property name for JSON param serialization
MaterialPass.inspect_fields = {
    "material": InspectField(
        path="material",
        label="Material",
        kind="tc_material",
    ),
}


def get_texture_inputs_for_material(material_name: str) -> List[Tuple[str, str]]:
    """
    Get list of texture inputs for a material's shader.

    Args:
        material_name: Name of the material.

    Returns:
        List of (input_name, socket_type) tuples for node inputs.
        input_name is the shader uniform name.  The graph socket name must
        stay identical to the material sampler so the compiled pass can bind
        the connected resource to the material texture slot instead of a
        separate ad-hoc slot.
    """
    if not material_name or material_name == "(None)":
        return []

    from termin.assets.resources import ResourceManager

    rm = ResourceManager.instance()
    material = rm.get_material(material_name)
    if material is None:
        log.warn(f"[get_texture_inputs_for_material] material '{material_name}' not found")
        return []

    shader_name = material.shader_name
    if not shader_name:
        log.warn(f"[get_texture_inputs_for_material] material '{material_name}' has no shader_name")
        return []

    program = rm.get_shader(shader_name)
    if program is None or not program.phases:
        log.warn(f"[get_texture_inputs_for_material] shader '{shader_name}' not found or has no phases")
        return []

    # Collect texture uniforms from first phase. Texture @property entries are
    # editable material fields and graph inputs for MaterialPass.
    inputs = []
    shader_uniforms = list(program.phases[0].uniforms) + list(program.phases[0].material_uniforms)
    for prop in shader_uniforms:
        if prop.property_type == "Texture":
            inputs.append((prop.name, "fbo"))

    return inputs


# Add as class method for backwards compatibility
MaterialPass.get_texture_inputs_for_material = staticmethod(get_texture_inputs_for_material)
