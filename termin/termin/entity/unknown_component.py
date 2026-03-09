"""
UnknownComponent utilities.

UnknownComponent is now implemented in C++ in termin-scene.
This module provides the upgrade function for converting UnknownComponents to real
components when their modules are loaded.
"""

from __future__ import annotations


def upgrade_unknown_components(scene) -> int:
    """
    Try to upgrade UnknownComponents to real components.

    Called after a module is loaded to convert placeholders to real components.

    Args:
        scene: Scene to process

    Returns:
        Number of components upgraded
    """
    if scene is None:
        return 0

    from termin.scene import upgrade_unknown_components as _upgrade_unknown_components

    stats = _upgrade_unknown_components(scene)
    return int(stats.upgraded)
