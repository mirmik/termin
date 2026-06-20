"""App ResourceManager extension.

The canonical standard SDK resource manager lives in
``termin.default_assets.resource_manager``. This package exposes the editor/app
manager extension used by app code that wants missing materials resolved to the
canonical ``termin.materials.UnknownMaterial`` visual fallback.

Usage:
    from termin.assets.resources import ResourceManager
    rm = ResourceManager.instance()
"""

from ._manager import ResourceManager
from termin_assets.resource_handle import set_resource_manager_factory


def _termin_app_resource_manager():
    return ResourceManager.instance()


set_resource_manager_factory(_termin_app_resource_manager)

__all__ = ["ResourceManager"]
