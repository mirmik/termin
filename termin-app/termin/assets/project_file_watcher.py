"""Compatibility wrapper for project asset watching.

New non-app code should import from termin_assets.project_file_watcher. This
module keeps Termin app defaults such as project ignored resource paths.
"""

from __future__ import annotations

from pathlib import Path

from termin_assets.preload import PreLoadResult
from termin_assets.project_file_watcher import (
    DEBOUNCE_DELAY_S,
    FilePreLoader,
    ProjectFileWatcher as BaseProjectFileWatcher,
)


def _termin_app_ignored_roots(project_root: Path) -> tuple[Path, ...]:
    from termin.project.ignored_paths import project_ignored_roots

    return project_ignored_roots(project_root)


class ProjectFileWatcher(BaseProjectFileWatcher):
    """Project watcher with Termin app project-settings ignore policy."""

    def __init__(self, on_resource_reloaded=None):
        super().__init__(
            on_resource_reloaded=on_resource_reloaded,
            ignored_roots_provider=_termin_app_ignored_roots,
        )


__all__ = [
    "DEBOUNCE_DELAY_S",
    "FilePreLoader",
    "PreLoadResult",
    "ProjectFileWatcher",
]
