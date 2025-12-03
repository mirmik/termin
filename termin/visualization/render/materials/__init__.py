"""Built-in material presets."""

from termin.visualization.render.materials.default_material import DefaultMaterial, default_shader
from termin.visualization.render.materials.pick_material import PickMaterial
from termin.visualization.render.materials.simple import ColorMaterial

__all__ = [
    "DefaultMaterial",
    "default_shader",
    "PickMaterial",
    "ColorMaterial",
]
