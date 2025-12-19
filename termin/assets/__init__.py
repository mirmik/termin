"""Asset management system for termin."""

from termin.assets.asset import Asset, Identifiable
from termin.assets.data_asset import DataAsset
from termin.assets.asset_registry import AssetRegistry
from termin.assets.resource_handle import ResourceHandle, ResourceKeeper
from termin.assets.resources import ResourceManager

__all__ = [
    "Asset",
    "Identifiable",
    "DataAsset",
    "AssetRegistry",
    "ResourceHandle",
    "ResourceKeeper",
    "ResourceManager",
]
