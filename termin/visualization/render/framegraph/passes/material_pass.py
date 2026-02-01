"""MaterialPass - Post-processing pass using a Material asset.

Re-exports C++ MaterialPass with Python-only utilities for editor.
"""

from __future__ import annotations

from typing import List, Tuple

from termin._native.render import MaterialPass
from termin.editor.inspect_field import InspectField
from termin._native import log

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
        input_name is derived from uniform name (u_depth -> depth).
        Includes u_input as "input" if shader uses it.
    """
    if not material_name or material_name == "(None)":
        return []

    from termin.visualization.core.resources import ResourceManager

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

    # Collect texture uniforms from first phase
    inputs = []
    for prop in program.phases[0].uniforms:
        if prop.property_type == "Texture":
            uniform_name = prop.name
            # Convert uniform name to input name: u_depth_texture -> depth_texture
            # u_input -> input (for standard post-effect input)
            if uniform_name.startswith("u_"):
                input_name = uniform_name[2:]
            else:
                input_name = uniform_name
            inputs.append((input_name, "fbo"))

    return inputs


# Add as class method for backwards compatibility
MaterialPass.get_texture_inputs_for_material = staticmethod(get_texture_inputs_for_material)
