"""Default file pre-loader registration for editor and player."""

from __future__ import annotations

from collections.abc import Callable

from tcbase import log

from termin.assets.resources import ResourceManager
from termin.editor_core.file_processors import (
    AudioPreLoader,
    ComponentFileProcessor,
    GLBPreLoader,
    GlslPreLoader,
    MaterialPreLoader,
    NavMeshPreLoader,
    PipelinePreLoader,
    PrefabPreLoader,
    ScenePipelinePreLoader,
    ShaderPreLoader,
    TexturePreLoader,
    UIPreLoader,
    VoxelGridPreLoader,
)
from termin.editor_core.plugin_preloader import PluginPreLoader
from termin.editor_core.project_file_watcher import FilePreLoader, ProjectFileWatcher


def _create_plugin_preloader(
    resource_manager: ResourceManager,
    type_id: str,
    on_resource_reloaded: Callable[[str, str], None] | None,
) -> PluginPreLoader:
    plugin = resource_manager.asset_type_plugins.get_import(type_id)
    if plugin is None:
        message = f"Asset import plugin '{type_id}' is not registered"
        log.error(message)
        raise RuntimeError(message)
    return PluginPreLoader(plugin, resource_manager, on_resource_reloaded=on_resource_reloaded)


def create_default_preloaders(
    resource_manager: ResourceManager,
    on_resource_reloaded: Callable[[str, str], None] | None = None,
) -> list[FilePreLoader]:
    return [
        GlslPreLoader(resource_manager, on_resource_reloaded=on_resource_reloaded),
        PipelinePreLoader(resource_manager, on_resource_reloaded=on_resource_reloaded),
        ScenePipelinePreLoader(resource_manager, on_resource_reloaded=on_resource_reloaded),
        ShaderPreLoader(resource_manager, on_resource_reloaded=on_resource_reloaded),
        TexturePreLoader(resource_manager, on_resource_reloaded=on_resource_reloaded),
        MaterialPreLoader(resource_manager, on_resource_reloaded=on_resource_reloaded),
        ComponentFileProcessor(resource_manager, on_resource_reloaded=on_resource_reloaded),
        _create_plugin_preloader(resource_manager, "mesh", on_resource_reloaded),
        GLBPreLoader(resource_manager, on_resource_reloaded=on_resource_reloaded),
        PrefabPreLoader(resource_manager, on_resource_reloaded=on_resource_reloaded),
        AudioPreLoader(resource_manager, on_resource_reloaded=on_resource_reloaded),
        NavMeshPreLoader(resource_manager, on_resource_reloaded=on_resource_reloaded),
        VoxelGridPreLoader(resource_manager, on_resource_reloaded=on_resource_reloaded),
        UIPreLoader(resource_manager, on_resource_reloaded=on_resource_reloaded),
    ]


def register_default_preloaders(
    watcher: ProjectFileWatcher,
    resource_manager: ResourceManager,
    on_resource_reloaded: Callable[[str, str], None] | None = None,
) -> None:
    for processor in create_default_preloaders(resource_manager, on_resource_reloaded):
        watcher.register_processor(processor)
