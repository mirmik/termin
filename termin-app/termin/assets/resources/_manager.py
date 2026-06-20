"""ResourceManager combining all mixins."""

from __future__ import annotations

from termin.default_assets.resource_accessors import DefaultResourceAccessorsMixin
from termin.default_assets.resource_manager import DefaultResourceManagerBase
from termin.default_assets.resource_serialization import DefaultSerializationMixin

from ._assets import AssetsMixin
from ._components import ComponentsMixin


class AppResourceManager(
    DefaultResourceManagerBase,
    AssetsMixin,
    ComponentsMixin,
    DefaultResourceAccessorsMixin,
    DefaultSerializationMixin,
):
    """
    App resource manager extension over the default runtime manager.

    Runtime/default asset ownership lives in ``termin.default_assets``. This
    class adds app-specific material fallback and visualization component/
    frame-pass registrations. Use ``ResourceManager`` as the legacy public app
    alias.
    """

    @classmethod
    def instance(cls) -> "AppResourceManager":
        instance = super().instance()

        from termin_assets import set_resource_manager_factory

        set_resource_manager_factory(cls.instance)
        return instance


ResourceManager = AppResourceManager

__all__ = ["AppResourceManager", "ResourceManager"]
