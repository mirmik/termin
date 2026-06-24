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


def configure_app_resource_manager_factory() -> None:
    """Register the app ResourceManager factory in an explicit bootstrap step."""
    from termin.bootstrap import configure_resource_manager_factory

    configure_resource_manager_factory(ResourceManager.instance)

__all__ = ["ResourceManager", "configure_app_resource_manager_factory"]
