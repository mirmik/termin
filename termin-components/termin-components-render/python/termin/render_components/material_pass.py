"""MaterialPass helpers owned by the render-components package."""

from __future__ import annotations

from typing import List, Tuple

from termin.inspect import InspectField
from termin.render_components import MaterialPass
from tcbase import log

__all__ = ["MaterialPass", "get_texture_inputs_for_material"]

# Key must match the property name for JSON param serialization.
MaterialPass.inspect_fields = {
    "material": InspectField(
        path="material",
        label="Material",
        kind="tc_material",
    ),
}


def get_texture_inputs_for_material(material_identifier: str) -> List[Tuple[str, str]]:
    """
    Get list of texture inputs for a material's shader.

    The graph socket name must stay identical to the material sampler so the
    compiled pass can bind the connected resource to the material texture slot
    instead of a separate ad-hoc slot.
    """
    if not material_identifier or material_identifier == "(None)":
        return []

    from termin_assets import get_resource_manager

    rm = get_resource_manager()
    if rm is None:
        message = "[get_texture_inputs_for_material] resource manager is not initialized"
        log.error(message)
        raise RuntimeError(message)

    asset = rm.get_material_asset_by_uuid(material_identifier)
    material = (
        rm.get_material_by_uuid(material_identifier)
        if asset is not None
        else rm.get_material(material_identifier)
    )
    if material is None:
        log.warn(f"[get_texture_inputs_for_material] material '{material_identifier}' not found")
        return []

    shader_name = material.shader_name
    if not shader_name:
        log.warn(f"[get_texture_inputs_for_material] material '{material_identifier}' has no shader_name")
        return []

    program = rm.get_shader(shader_name)
    if program is None:
        log.warn(f"[get_texture_inputs_for_material] shader '{shader_name}' not found")
        return []

    inputs = []
    for prop in program.material_properties:
        if prop.property_type == "Texture":
            inputs.append((prop.name, "fbo"))

    return inputs


MaterialPass.get_texture_inputs_for_material = staticmethod(get_texture_inputs_for_material)
