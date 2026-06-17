"""ResourceManager package.

This module provides the ResourceManager singleton for managing all resources:
materials, meshes, textures, shaders, components, pipelines, etc.

Usage:
    from termin.assets.resources import ResourceManager
    rm = ResourceManager.instance()
"""

from ._handle_accessors import HandleAccessors
from ._manager import ResourceManager
from termin_assets.resource_handle import set_resource_manager_factory


def _termin_app_resource_manager():
    return ResourceManager.instance()


set_resource_manager_factory(_termin_app_resource_manager)

__all__ = ["ResourceManager", "HandleAccessors"]
