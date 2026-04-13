"""ResourceManager package.

This module provides the ResourceManager singleton for managing all resources:
materials, meshes, textures, shaders, components, pipelines, etc.

Usage:
    from termin.assets.resources import ResourceManager
    rm = ResourceManager.instance()
"""

from ._handle_accessors import HandleAccessors
from ._manager import ResourceManager

__all__ = ["ResourceManager", "HandleAccessors"]
