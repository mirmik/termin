"""Shared asset-system contracts."""

from termin_assets.plugin import (
    AssetContext,
    AssetImportPlugin,
    AssetRuntimePlugin,
    AssetTypePlugin,
    AssetTypeRegistry,
)
from termin_assets.preload import PreLoadResult

__all__ = [
    "AssetContext",
    "AssetImportPlugin",
    "AssetRuntimePlugin",
    "AssetTypePlugin",
    "AssetTypeRegistry",
    "PreLoadResult",
]
