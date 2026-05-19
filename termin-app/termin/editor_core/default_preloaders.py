"""Default file pre-loader registration for editor and player."""

from __future__ import annotations

from collections.abc import Callable

from tcbase import log

from termin.assets.resources import ResourceManager
from termin.editor_core.file_processors import (
    ComponentFileProcessor,
    GLBPreLoader,
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
        _create_plugin_preloader(resource_manager, "glsl", on_resource_reloaded),
        _create_plugin_preloader(resource_manager, "pipeline", on_resource_reloaded),
        _create_plugin_preloader(resource_manager, "scene_pipeline", on_resource_reloaded),
        _create_plugin_preloader(resource_manager, "shader", on_resource_reloaded),
        _create_plugin_preloader(resource_manager, "texture", on_resource_reloaded),
        _create_plugin_preloader(resource_manager, "material", on_resource_reloaded),
        ComponentFileProcessor(resource_manager, on_resource_reloaded=on_resource_reloaded),
        _create_plugin_preloader(resource_manager, "mesh", on_resource_reloaded),
        GLBPreLoader(resource_manager, on_resource_reloaded=on_resource_reloaded),
        _create_plugin_preloader(resource_manager, "prefab", on_resource_reloaded),
        _create_plugin_preloader(resource_manager, "audio_clip", on_resource_reloaded),
        _create_plugin_preloader(resource_manager, "navmesh", on_resource_reloaded),
        _create_plugin_preloader(resource_manager, "voxel_grid", on_resource_reloaded),
        _create_plugin_preloader(resource_manager, "ui", on_resource_reloaded),
    ]


def register_default_preloaders(
    watcher: ProjectFileWatcher,
    resource_manager: ResourceManager,
    on_resource_reloaded: Callable[[str, str], None] | None = None,
) -> None:
    for processor in create_default_preloaders(resource_manager, on_resource_reloaded):
        watcher.register_processor(processor)
