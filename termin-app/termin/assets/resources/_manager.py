"""ResourceManager combining all mixins."""

from __future__ import annotations

from termin.default_assets.resource_api import DefaultAssetResourceMixin
from termin.default_assets.resource_accessors import DefaultResourceAccessorsMixin
from termin.default_assets.resource_manager import DefaultResourceManagerBase
from termin.default_assets.resource_serialization import DefaultSerializationMixin

from ._components import ComponentsMixin


class AppResourceManager(
    DefaultResourceManagerBase,
    DefaultAssetResourceMixin,
    ComponentsMixin,
    DefaultResourceAccessorsMixin,
    DefaultSerializationMixin,
):
    """
    App resource manager extension over the default runtime manager.

    Runtime/default asset ownership lives in ``termin.default_assets``. This
    class keeps the legacy public app alias and app builtin-extension point.
    """

    @classmethod
    def instance(cls) -> "AppResourceManager":
        instance = super().instance()

        from termin_assets import set_resource_manager_factory

        set_resource_manager_factory(cls.instance)
        return instance


ResourceManager = AppResourceManager

__all__ = ["AppResourceManager", "ResourceManager"]
