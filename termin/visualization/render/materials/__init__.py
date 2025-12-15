"""Built-in material presets."""

from termin.visualization.render.materials.default_material import DefaultMaterial, default_shader
from termin.visualization.render.materials.pbr_material import PBRMaterial, pbr_shader
from termin.visualization.render.materials.advanced_pbr_material import AdvancedPBRMaterial, advanced_pbr_shader
from termin.visualization.render.materials.pick_material import PickMaterial
from termin.visualization.render.materials.simple import ColorMaterial

__all__ = [
    "DefaultMaterial",
    "default_shader",
    "PBRMaterial",
    "pbr_shader",
    "AdvancedPBRMaterial",
    "advanced_pbr_shader",
    "PickMaterial",
    "ColorMaterial",
]
