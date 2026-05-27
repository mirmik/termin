"""Compatibility re-export for ResourceHandle."""

from termin_assets.resource_handle import ResourceHandle, set_resource_manager_factory


def _termin_app_resource_manager():
    from termin.assets.resources import ResourceManager

    return ResourceManager.instance()


set_resource_manager_factory(_termin_app_resource_manager)

__all__ = ["ResourceHandle", "set_resource_manager_factory"]
