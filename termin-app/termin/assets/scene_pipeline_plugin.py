"""Compatibility re-export for scene pipeline asset plugins.

Canonical module: :mod:`termin.render.scene_pipeline_plugin`.
"""

from termin.render.scene_pipeline_plugin import (
    ScenePipelineAssetPlugin,
    ScenePipelineImportPlugin,
    ScenePipelineRuntimePlugin,
    register_scene_pipeline_asset_plugin,
    register_scene_pipeline_import_plugin,
    register_scene_pipeline_runtime_plugin,
)

__all__ = [
    "ScenePipelineAssetPlugin",
    "ScenePipelineImportPlugin",
    "ScenePipelineRuntimePlugin",
    "register_scene_pipeline_asset_plugin",
    "register_scene_pipeline_import_plugin",
    "register_scene_pipeline_runtime_plugin",
]
