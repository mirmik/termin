"""Compatibility re-export for project asset watching."""

from termin.assets.project_file_watcher import (
    DEBOUNCE_DELAY_S,
    FilePreLoader,
    PreLoadResult,
    ProjectFileWatcher,
)

__all__ = [
    "DEBOUNCE_DELAY_S",
    "FilePreLoader",
    "PreLoadResult",
    "ProjectFileWatcher",
]
