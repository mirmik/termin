"""Built-in material presets."""

from termin.visualization.render.materials.default_material import DefaultMaterial, default_shader
from termin.visualization.render.materials.pbr_material import PBRMaterial, pbr_shader
from termin.visualization.render.materials.pick_material import PickMaterial
from termin.visualization.render.materials.simple import ColorMaterial
from termin.visualization.render.materials.grid_material import GridMaterial, grid_shader
from termin.visualization.render.materials.unknown_material import UnknownMaterial, get_unknown_shader

__all__ = [
    "DefaultMaterial",
    "default_shader",
    "PBRMaterial",
    "pbr_shader",
    "PickMaterial",
    "ColorMaterial",
    "GridMaterial",
    "grid_shader",
    "UnknownMaterial",
    "get_unknown_shader",
]
