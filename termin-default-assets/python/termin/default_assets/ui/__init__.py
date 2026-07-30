"""Default UI asset adapters."""

from .document_asset import UiDocumentSourceAsset
from .asset import UIAsset
from .handle import UIHandle
from .asset_plugin import (
    UIAssetPlugin,
    UIImportPlugin,
    UIRuntimePlugin,
    create_import_plugin,
    create_runtime_plugin,
    register_ui_asset_plugin,
    register_ui_import_plugin,
    register_ui_runtime_plugin,
)

__all__ = [
    "UIAsset",
    "UIHandle",
    "UiDocumentSourceAsset",
    "UIAssetPlugin",
    "UIImportPlugin",
    "UIRuntimePlugin",
    "create_import_plugin",
    "create_runtime_plugin",
    "register_ui_asset_plugin",
    "register_ui_import_plugin",
    "register_ui_runtime_plugin",
]
