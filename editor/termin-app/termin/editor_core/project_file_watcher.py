"""Editor project asset watcher policy."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from termin_assets.preload import PreLoadResult
from termin_assets.project_file_watcher import (
    DEBOUNCE_DELAY_S,
    FilePreLoader,
    ProjectFileWatcher as BaseProjectFileWatcher,
)

if TYPE_CHECKING:
    from termin.editor_core.file_processors import ComponentFileProcessor


_logger = logging.getLogger(__name__)


def _termin_editor_ignored_roots(project_root: Path) -> tuple[Path, ...]:
    from termin.project.ignored_paths import project_ignored_roots

    return project_ignored_roots(project_root)


class ProjectFileWatcher(BaseProjectFileWatcher):
    """Project watcher with Termin editor project-settings ignore policy."""

    def __init__(self, on_resource_reloaded=None):
        super().__init__(
            on_resource_reloaded=on_resource_reloaded,
            ignored_roots_provider=_termin_editor_ignored_roots,
        )


def create_editor_project_file_watcher(
    resource_manager,
    *,
    on_resource_reloaded: Callable[[str, str], None] | None = None,
) -> tuple[ProjectFileWatcher, "ComponentFileProcessor"]:
    """Create the production watcher and register all editor file processors."""
    from termin.default_assets.default_preloaders import (
        register_default_preloaders as register_default_asset_preloaders,
    )
    from termin.editor_core.file_processors import (
        ComponentFileProcessor,
        ModuleFileProcessor,
        ModuleInputFileProcessor,
    )

    try:
        watcher = ProjectFileWatcher(on_resource_reloaded=on_resource_reloaded)
        watcher.register_processor(
            ModuleFileProcessor(
                resource_manager,
                on_resource_reloaded=on_resource_reloaded,
            )
        )
        watcher.register_processor(
            ModuleInputFileProcessor(
                resource_manager,
                on_resource_reloaded=on_resource_reloaded,
            )
        )
        register_default_asset_preloaders(
            watcher,
            resource_manager,
            on_resource_reloaded,
        )
        component_processor = ComponentFileProcessor(
            resource_manager,
            on_resource_reloaded=on_resource_reloaded,
        )
        watcher.register_processor(component_processor)
        return watcher, component_processor
    except Exception:
        _logger.exception("Failed to create the editor project file watcher")
        raise


__all__ = [
    "DEBOUNCE_DELAY_S",
    "FilePreLoader",
    "PreLoadResult",
    "ProjectFileWatcher",
    "create_editor_project_file_watcher",
]
