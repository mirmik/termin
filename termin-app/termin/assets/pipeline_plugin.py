"""Compatibility re-export for render pipeline asset plugins.

Canonical module: :mod:`termin.default_assets.render.pipeline_plugin`.
"""

from termin.default_assets.render.pipeline_plugin import (
    PipelineAssetPlugin,
    PipelineImportPlugin,
    PipelineRuntimePlugin,
    register_pipeline_asset_plugin,
    register_pipeline_import_plugin,
    register_pipeline_runtime_plugin,
)

__all__ = [
    "PipelineAssetPlugin",
    "PipelineImportPlugin",
    "PipelineRuntimePlugin",
    "register_pipeline_asset_plugin",
    "register_pipeline_import_plugin",
    "register_pipeline_runtime_plugin",
]
