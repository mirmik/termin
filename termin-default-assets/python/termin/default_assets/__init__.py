"""Default asset adapters for Termin."""

from termin.default_assets.handle_accessors import HandleAccessors
from termin.default_assets.resource_accessors import DefaultResourceAccessorsMixin
from termin.default_assets.resource_manager import DefaultResourceManager
from termin.default_assets.resource_manager import DefaultResourceManagerBase

__all__ = [
    "DefaultResourceAccessorsMixin",
    "DefaultResourceManager",
    "DefaultResourceManagerBase",
    "HandleAccessors",
]
