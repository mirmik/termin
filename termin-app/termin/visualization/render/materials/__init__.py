"""Material fallback helpers.

Legacy preset material helpers were removed after their internal consumers moved
to shader/catalog driven materials. ``UnknownMaterial`` remains app-owned
because the editor ResourceManager uses it for missing material visualization.
"""

from termin.visualization.render.materials.unknown_material import (
    UnknownMaterial,
    create_unknown_material,
)

__all__ = [
    "UnknownMaterial",
    "create_unknown_material",
]
