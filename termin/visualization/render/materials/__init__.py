"""Built-in material presets.

All material classes now return TcMaterial instances.
Use the create_* factory functions for explicit material creation.
"""

from termin.visualization.render.materials.default_material import (
    DefaultMaterial,
    create_default_material,
)
from termin.visualization.render.materials.pbr_material import (
    PBRMaterial,
    create_pbr_material,
)
from termin.visualization.render.materials.pick_material import (
    PickMaterial,
    create_pick_material,
)
from termin.visualization.render.materials.simple import (
    ColorMaterial,
    UnlitMaterial,
    create_color_material,
    create_unlit_material,
)
from termin.visualization.render.materials.grid_material import (
    GridMaterial,
    create_grid_material,
)
from termin.visualization.render.materials.unknown_material import (
    UnknownMaterial,
    create_unknown_material,
)
from termin.visualization.render.materials.shadow_material import (
    ShadowMaterial,
    create_shadow_material,
)
from termin.visualization.render.materials.depth_material import (
    DepthMaterial,
    create_depth_material,
)
from termin.visualization.render.materials.skinned_material import (
    SkinnedMaterial,
    create_skinned_material,
)

__all__ = [
    # Material classes (return TcMaterial)
    "DefaultMaterial",
    "PBRMaterial",
    "PickMaterial",
    "ColorMaterial",
    "UnlitMaterial",
    "GridMaterial",
    "UnknownMaterial",
    "ShadowMaterial",
    "DepthMaterial",
    "SkinnedMaterial",
    # Factory functions
    "create_default_material",
    "create_pbr_material",
    "create_pick_material",
    "create_color_material",
    "create_unlit_material",
    "create_grid_material",
    "create_unknown_material",
    "create_shadow_material",
    "create_depth_material",
    "create_skinned_material",
]
