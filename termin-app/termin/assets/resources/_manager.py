"""ResourceManager combining all mixins."""

from __future__ import annotations

from ._base import ResourceManagerBase
from ._assets import AssetsMixin
from ._components import ComponentsMixin
from ._accessors import AccessorsMixin
from ._serialization import SerializationMixin


class AppResourceManager(
    ResourceManagerBase,
    AssetsMixin,
    ComponentsMixin,
    AccessorsMixin,
    SerializationMixin,
):
    """
    App resource manager extension over the default runtime manager.

    Runtime/default asset ownership lives in ``termin.default_assets``. This
    class adds app-specific material fallback and visualization component/
    frame-pass registrations. Use ``ResourceManager`` as the legacy public app
    alias.
    """
    pass


ResourceManager = AppResourceManager

__all__ = ["AppResourceManager", "ResourceManager"]
