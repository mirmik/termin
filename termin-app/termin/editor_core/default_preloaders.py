"""Editor compatibility layer for default file pre-loader registration."""

from __future__ import annotations

from collections.abc import Callable

from termin.editor_core.resource_manager import ResourceManager
from termin_assets.project_file_watcher import FilePreLoader, ProjectFileWatcher
from termin.default_assets.default_preloaders import (
    create_default_preloaders as create_default_asset_preloaders,
)
from termin.editor_core.file_processors import ComponentFileProcessor
from termin.editor_core.file_processors import ModuleFileProcessor
from termin.editor_core.file_processors import ModuleInputFileProcessor


def create_default_preloaders(
    resource_manager: ResourceManager,
    on_resource_reloaded: Callable[[str, str], None] | None = None,
) -> list[FilePreLoader]:
    return [
        ModuleFileProcessor(resource_manager, on_resource_reloaded=on_resource_reloaded),
        ModuleInputFileProcessor(resource_manager, on_resource_reloaded=on_resource_reloaded),
        *create_default_asset_preloaders(resource_manager, on_resource_reloaded),
        ComponentFileProcessor(resource_manager, on_resource_reloaded=on_resource_reloaded),
    ]


def register_default_preloaders(
    watcher: ProjectFileWatcher,
    resource_manager: ResourceManager,
    on_resource_reloaded: Callable[[str, str], None] | None = None,
) -> None:
    watcher.set_external_asset_catalog(resource_manager.external_assets)
    for processor in create_default_preloaders(resource_manager, on_resource_reloaded):
        watcher.register_processor(processor)
