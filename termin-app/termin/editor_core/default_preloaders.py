"""Default file pre-loader registration for editor and player."""

from __future__ import annotations

from collections.abc import Callable

from termin.assets.resources import ResourceManager
from termin.editor_core.file_processors import (
    AudioPreLoader,
    ComponentFileProcessor,
    GLBPreLoader,
    GlslPreLoader,
    MaterialPreLoader,
    MeshPreLoader,
    NavMeshPreLoader,
    PipelinePreLoader,
    PrefabPreLoader,
    ScenePipelinePreLoader,
    ShaderPreLoader,
    TexturePreLoader,
    UIPreLoader,
    VoxelGridPreLoader,
)
from termin.editor_core.project_file_watcher import FilePreLoader, ProjectFileWatcher


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
        MeshPreLoader(resource_manager, on_resource_reloaded=on_resource_reloaded),
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
